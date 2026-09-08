import os
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import argparse
import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import datasets, transforms
from torchvision.models import mobilenet_v3_small, MobileNet_V3_Small_Weights
from torch.utils.data import DataLoader, random_split
from pathlib import Path

def train_model(dataset_dir: str, output_onnx: str, epochs: int = 15, batch_size: int = 32):
    print(f"Loading dataset from {dataset_dir}...")
    
    # Check if dataset exists and has classes
    if not os.path.exists(dataset_dir):
        print(f"Error: Dataset directory '{dataset_dir}' does not exist.")
        return
        
    # Data augmentation and normalization
    train_transforms = transforms.Compose([
        transforms.Resize((48, 48)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomVerticalFlip(),
        transforms.RandomRotation(15),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    val_transforms = transforms.Compose([
        transforms.Resize((48, 48)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    try:
        full_dataset = datasets.ImageFolder(dataset_dir)
    except Exception as e:
        print(f"Failed to load dataset: {e}")
        print("Make sure you have run the extract_and_label.py tool and labeled some images!")
        return
        
    print(f"Found {len(full_dataset)} images belonging to {len(full_dataset.classes)} classes: {full_dataset.classes}")
    if len(full_dataset) < 10:
        print("Warning: Dataset is very small. Training might overfit severely or fail.")
        
    # Split into 80% train, 20% validation
    train_size = int(0.8 * len(full_dataset))
    val_size = len(full_dataset) - train_size
    train_dataset, val_dataset = random_split(full_dataset, [train_size, val_size])
    
    # Apply different transforms
    train_dataset.dataset.transform = train_transforms
    
    # Create a separate dataset object for validation to apply val_transforms
    val_dataset_eval = datasets.ImageFolder(dataset_dir, transform=val_transforms)
    # We must manually map the validation indices
    val_dataset_eval = torch.utils.data.Subset(val_dataset_eval, val_dataset.indices)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset_eval, batch_size=batch_size, shuffle=False)

    print("Initializing MobileNetV3-Small...")
    model = mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.DEFAULT)
    
    # Replace the classification head
    # 2 classes: usually freckle and noise
    num_classes = len(full_dataset.classes)
    model.classifier[3] = nn.Linear(model.classifier[3].in_features, num_classes)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if torch.backends.mps.is_available():
        device = torch.device("mps")
        
    print(f"Training on device: {device}")
    model = model.to(device)
    
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    best_acc = 0.0
    
    for epoch in range(epochs):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0
        
        for inputs, labels in train_loader:
            inputs, labels = inputs.to(device), labels.to(device)
            
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item() * inputs.size(0)
            _, predicted = torch.max(outputs, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
            
        epoch_loss = running_loss / total if total > 0 else 0
        epoch_acc = correct / total if total > 0 else 0
        
        # Validation
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        
        with torch.no_grad():
            for inputs, labels in val_loader:
                inputs, labels = inputs.to(device), labels.to(device)
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                
                val_loss += loss.item() * inputs.size(0)
                _, predicted = torch.max(outputs, 1)
                val_total += labels.size(0)
                val_correct += (predicted == labels).sum().item()
                
        val_epoch_loss = val_loss / val_total if val_total > 0 else 0
        val_epoch_acc = val_correct / val_total if val_total > 0 else 0
        
        print(f"Epoch {epoch+1}/{epochs} | "
              f"Train Loss: {epoch_loss:.4f} Acc: {epoch_acc:.4f} | "
              f"Val Loss: {val_epoch_loss:.4f} Acc: {val_epoch_acc:.4f}")
              
        if val_epoch_acc >= best_acc:
            best_acc = val_epoch_acc
            
            # Export to ONNX
            print(f"  -> New best model! Exporting to {output_onnx}...")
            model.eval()
            model.to("cpu")
            dummy_input = torch.randn(1, 3, 48, 48)
            os.makedirs(os.path.dirname(output_onnx), exist_ok=True)
            
            torch.onnx.export(
                model, 
                dummy_input, 
                output_onnx, 
                export_params=True, 
                opset_version=11, 
                do_constant_folding=True, 
                input_names=['input'], 
                output_names=['output'], 
                dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}}
            )
            model.to(device) # put back for next epoch

    print("Training complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_dir", type=str, default="dataset", help="Directory containing labeled classes")
    parser.add_argument("--epochs", type=int, default=15, help="Number of training epochs")
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    model_path = project_root / "models" / "freckle_classifier.onnx"
    
    train_model(args.dataset_dir, str(model_path), epochs=args.epochs)
