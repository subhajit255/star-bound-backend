import argparse
import cv2
import numpy as np
from pathlib import Path
from detection.pipeline import detect_image, _read_image

def extract_and_label(raw_dir: str, dataset_dir: str):
    raw_path = Path(raw_dir)
    ds_path = Path(dataset_dir)
    
    freckle_dir = ds_path / "freckle"
    noise_dir = ds_path / "noise"
    
    freckle_dir.mkdir(parents=True, exist_ok=True)
    noise_dir.mkdir(parents=True, exist_ok=True)
    
    freckle_count = len(list(freckle_dir.glob("*.jpg")))
    noise_count = len(list(noise_dir.glob("*.jpg")))
    
    image_paths = list(raw_path.glob("*.jpg")) + list(raw_path.glob("*.png")) + list(raw_path.glob("*.jpeg"))
    if not image_paths:
        print(f"No images found in {raw_dir}")
        return
        
    print(f"Found {len(image_paths)} images in {raw_dir}.")
    print(f"Current dataset size: {freckle_count} freckles, {noise_count} noises.")
    print("Instructions:")
    print(" - Press 'y' if the crop is a valid freckle/mole.")
    print(" - Press 'n' if it is noise (pimple, shadow, hair).")
    print(" - Press 's' to skip this crop.")
    print(" - Press 'q' to quit labeling and save progress.")
    
    for img_path in image_paths:
        print(f"Processing {img_path.name}...")
        try:
            # Bypass NN so we get ALL candidates found by the CV pipeline
            result = detect_image(img_path, skip_nn=True)
        except Exception as e:
            print(f"Failed to process {img_path.name}: {e}")
            continue
            
        if not result.points:
            continue
            
        image = _read_image(img_path)
        height, width = image.shape[:2]
        
        for p in result.points:
            xi, yi = int(round(p.x)), int(round(p.y))
            r = 24  # We want a 48x48 crop
            
            y1, y2 = max(0, yi - r), min(height, yi + r)
            x1, x2 = max(0, xi - r), min(width, xi + r)
            
            crop = image[y1:y2, x1:x2]
            
            # Pad if near edge to ensure 48x48
            if crop.shape[0] < 48 or crop.shape[1] < 48:
                pad_y = 48 - crop.shape[0]
                pad_x = 48 - crop.shape[1]
                crop = cv2.copyMakeBorder(crop, 0, pad_y, 0, pad_x, cv2.BORDER_CONSTANT, value=[0, 0, 0])
                
            # Resize for display so it's not tiny
            display_crop = cv2.resize(crop, (192, 192), interpolation=cv2.INTER_NEAREST)
            
            # Add crosshair for context
            cv2.line(display_crop, (96, 80), (96, 112), (0, 255, 0), 1)
            cv2.line(display_crop, (80, 96), (112, 96), (0, 255, 0), 1)
            
            cv2.imshow("Label Crop (Y/N/S/Q)", display_crop)
            key = cv2.waitKey(0) & 0xFF
            
            if key == ord('y'):
                out_path = freckle_dir / f"{img_path.stem}_{xi}_{yi}.jpg"
                cv2.imwrite(str(out_path), crop)
                freckle_count += 1
            elif key == ord('n'):
                out_path = noise_dir / f"{img_path.stem}_{xi}_{yi}.jpg"
                cv2.imwrite(str(out_path), crop)
                noise_count += 1
            elif key == ord('q'):
                print(f"Quitting. Final counts: {freckle_count} freckles, {noise_count} noises.")
                cv2.destroyAllWindows()
                return
            else:
                # Skipped
                pass
                
    cv2.destroyAllWindows()
    print(f"Finished! Final counts: {freckle_count} freckles, {noise_count} noises.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw_dir", type=str, default="raw_images", help="Folder with raw skin photos")
    parser.add_argument("--dataset_dir", type=str, default="dataset", help="Output folder for labeled crops")
    args = parser.parse_args()
    
    extract_and_label(args.raw_dir, args.dataset_dir)
