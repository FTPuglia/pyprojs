import tkinter as tk
from tkinter import filedialog, simpledialog
from PIL import Image, ImageTk, ImageEnhance, ImageChops, ImageFilter # type: ignore
import os

# Global variables to store the original image and its Tkinter version
original_img = None
tk_img = None
image_label = None # Will be initialized later
root = None        # Will be initialized later
current_display_img = None # To hold the currently processed image for saving

# Variables to store current slider values
contrast_var = None
brightness_var = None
hue_var = None
sharpness_var = None
blur_var = None

# A helper function to detect and load files, including conversion
def load_image_from_path(file_path):
    """
    Loads an image from a given file path, converting it if necessary.
    Handles .webm files. .avif files are handled automatically if the
    pillow-avif-plugin is installed.
    """
    try:
        if file_path.lower().endswith(('.webm')):
            # Handle .webm files by converting the first frame
            try:
                from moviepy.editor import VideoFileClip # type: ignore
                print("Converting .webm video to an image frame...")
                clip = VideoFileClip(file_path)
                # Convert the first frame to a Pillow Image object
                frame = clip.get_frame(0)
                clip.close()
                return Image.fromarray(frame)
            except ImportError:
                print("Error: moviepy is not installed. Cannot open .webm files.")
                return None
            except Exception as e:
                print(f"An error occurred during .webm conversion: {e}")
                return None
        
        else:
            # Open a regular image file with Pillow.
            # This will automatically handle .avif if pillow-avif-plugin is installed.
            return Image.open(file_path)
            
    except Exception as e:
        print(f"An error occurred while loading the image: {e}")
        return None

def apply_adjustments(event=None):
    """
    Applies contrast, brightness, hue, sharpness, and blur adjustments to the original image
    and updates the displayed image in real-time.
    """
    global original_img, tk_img, image_label, root, current_display_img

    if original_img is None:
        return

    # Get current values from sliders
    contrast_factor = contrast_var.get()
    brightness_factor = brightness_var.get()
    hue_factor = hue_var.get()
    sharpness_factor = sharpness_var.get()
    blur_factor = blur_var.get()

    # Create a working copy of the original image
    processed_img = original_img.copy()

    # 1. Apply Contrast
    enhancer = ImageEnhance.Contrast(processed_img)
    processed_img = enhancer.enhance(contrast_factor)

    # 2. Apply Brightness
    enhancer = ImageEnhance.Brightness(processed_img)
    processed_img = enhancer.enhance(brightness_factor)
    
    # 3. Apply Sharpness
    enhancer = ImageEnhance.Sharpness(processed_img)
    processed_img = enhancer.enhance(sharpness_factor)
    
    # 4. Apply Gaussian Blur
    if blur_factor > 0:
        processed_img = processed_img.filter(ImageFilter.GaussianBlur(radius=blur_factor))

    # 5. Apply Hue (The corrected and working method)
    if hue_factor != 0:
        # Convert the image to the HSV color space
        hsv_img = processed_img.convert('HSV')
        
        # Split the HSV image into its H, S, and V channels
        h, s, v = hsv_img.split()
        
        # Use a point operation to shift the hue values.
        # This is a much faster and more accurate way to manipulate hue.
        # The value is mapped from the slider range.
        hue_shift = int(hue_factor * 2.55)  # Scale -100..100 to -255..255
        h = h.point(lambda p: (p + hue_shift) % 256)
        
        # Merge the channels back together
        hsv_img = Image.merge('HSV', (h, s, v))
        
        # Convert the image back to RGB for display
        processed_img = hsv_img.convert('RGB')
    
    # Store the processed image in a global variable
    current_display_img = processed_img.copy()

    # Resize the processed image to fit in the window while maintaining aspect ratio
    display_img = processed_img.copy()
    display_img.thumbnail((500, 500), Image.Resampling.LANCZOS)
    
    # Convert the Pillow image to a Tkinter-compatible format
    tk_img = ImageTk.PhotoImage(display_img)
    
    # Update the image label
    image_label.config(image=tk_img)
    image_label.image = tk_img  # Keep a reference to prevent garbage collection

def upscale_image():
    """
    Upscales the current image using a nearest-neighbor algorithm for
    a pixel-perfect result.
    """
    global original_img

    if original_img is None:
        return

    factor = simpledialog.askinteger("Upscale Factor", "Enter an integer scaling factor (e.g., 2, 3, 4):",
                                    parent=root, minvalue=1)

    if factor:
        try:
            # Get the current dimensions
            width, height = original_img.size

            # Calculate the new dimensions
            new_width = width * factor
            new_height = height * factor

            # Resize the original image with the nearest neighbor algorithm
            upscaled_image = original_img.resize((new_width, new_height), Image.Resampling.NEAREST)

            # Update the original_img
            original_img = upscaled_image

            # Re-apply adjustments to update the display
            apply_adjustments()
            print(f"Image upscaled by a factor of {factor} to {new_width}x{new_height}.")

        except Exception as e:
            print(f"An error occurred while upscaling the image: {e}")

def downscale_image():
    """
    Downscales the current image by a user-defined factor.
    """
    global original_img

    if original_img is None:
        return

    factor = simpledialog.askinteger("Downscale Factor", "Enter an integer scaling factor (e.g., 2, 3, 4):",
                                    parent=root, minvalue=1)
    
    if factor:
        try:
            # Get the current dimensions
            width, height = original_img.size

            # Calculate the new dimensions
            new_width = width // factor
            new_height = height // factor
            
            # Ensure dimensions are not zero
            if new_width == 0 or new_height == 0:
                print("Downscale factor is too large. Image dimensions would be zero.")
                return

            # Resize the original image with the LANCZOS algorithm for a high-quality result
            downscaled_image = original_img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Update the original_img
            original_img = downscaled_image

            # Re-apply adjustments to update the display
            apply_adjustments()
            print(f"Image downscaled by a factor of {factor} to {new_width}x{new_height}.")

        except Exception as e:
            print(f"An error occurred while downscaling the image: {e}")
            
def select_image():
    """
    Opens a file dialog for the user to select an image,
    loads it, and sets up the viewer.
    """
    global original_img, tk_img, root

    file_path = filedialog.askopenfilename(
        title="Select an Image File",
        filetypes=[
            ("Image Files", "*.png *.jpg *.jpeg *.gif *.bmp *.tiff *.avif *.webm"),
            ("All Files", "*.*")
        ]
    )

    if file_path:
        original_img = load_image_from_path(file_path)

        if original_img:
            # Reset sliders to default values for a new image
            contrast_var.set(1.0)
            brightness_var.set(1.0)
            hue_var.set(0)
            sharpness_var.set(1.0)
            blur_var.set(0.0)
            
            # Apply adjustments (which will display the image)
            apply_adjustments()
            root.title(f"Image Editor - {os.path.basename(file_path)}")
        else:
            print("Failed to load image. Check the console for errors.")
            image_label.config(image='', text="Error: Failed to load image.")
            original_img = None

def reset_sliders():
    """Resets all sliders to their default (original image) values."""
    contrast_var.set(1.0)
    brightness_var.set(1.0)
    hue_var.set(0)
    sharpness_var.set(1.0)
    blur_var.set(0.0)
    apply_adjustments() # Re-apply to show the original image

def save_image():
    """
    Opens a file dialog for the user to select a save location and filename,
    then saves the currently displayed image.
    """
    global current_display_img
    
    if current_display_img is None:
        print("No image to save.")
        return
        
    file_path = filedialog.asksaveasfilename(
        defaultextension=".png",
        filetypes=[
            ("PNG files", "*.png"),
            ("JPEG files", "*.jpg"),
            ("ICO files", "*.ico"),
            ("All files", "*.*")
        ]
    )

    if file_path:
        try:
            current_display_img.save(file_path)
            print(f"Image successfully saved to {file_path}")
        except Exception as e:
            print(f"An error occurred while saving the image: {e}")

# Main application setup
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Image Editor")
    root.geometry("800x700")

    # --- Control Frame (Top) ---
    control_frame = tk.Frame(root)
    control_frame.pack(pady=10)

    select_button = tk.Button(
        control_frame,
        text="Select Image",
        command=select_image
    )
    select_button.pack(side=tk.LEFT, padx=5)

    save_button = tk.Button(
        control_frame,
        text="Save Image",
        command=save_image
    )
    save_button.pack(side=tk.LEFT, padx=5)
    
    upscale_button = tk.Button(
        control_frame,
        text="Upscale Image",
        command=upscale_image
    )
    upscale_button.pack(side=tk.LEFT, padx=5)

    downscale_button = tk.Button(
        control_frame,
        text="Downscale Image",
        command=downscale_image
    )
    downscale_button.pack(side=tk.LEFT, padx=5)
    
    reset_button = tk.Button(
        control_frame,
        text="Reset All",
        command=reset_sliders
    )
    reset_button.pack(side=tk.LEFT, padx=5)

    # --- Sliders Frame (Below controls, Above image) ---
    sliders_frame = tk.Frame(root)
    sliders_frame.pack(pady=10, fill=tk.X)

    # Contrast Slider
    contrast_var = tk.DoubleVar(value=1.0)
    contrast_label = tk.Label(sliders_frame, text="Contrast:")
    contrast_label.pack(side=tk.LEFT, padx=5)
    contrast_slider = tk.Scale(
        sliders_frame,
        from_=0.1, to=3.0, resolution=0.01,
        orient=tk.HORIZONTAL,
        variable=contrast_var,
        command=apply_adjustments
    )
    contrast_slider.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

    # Brightness Slider
    brightness_var = tk.DoubleVar(value=1.0)
    brightness_label = tk.Label(sliders_frame, text="Brightness:")
    brightness_label.pack(side=tk.LEFT, padx=5)
    brightness_slider = tk.Scale(
        sliders_frame,
        from_=0.1, to=3.0, resolution=0.01,
        orient=tk.HORIZONTAL,
        variable=brightness_var,
        command=apply_adjustments
    )
    brightness_slider.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

    # Sharpness Slider
    sharpness_var = tk.DoubleVar(value=1.0)
    sharpness_label = tk.Label(sliders_frame, text="Sharpness:")
    sharpness_label.pack(side=tk.LEFT, padx=5)
    sharpness_slider = tk.Scale(
        sliders_frame,
        from_=0.0, to=2.0, resolution=0.01,
        orient=tk.HORIZONTAL,
        variable=sharpness_var,
        command=apply_adjustments
    )
    sharpness_slider.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

    # Hue Slider
    hue_var = tk.IntVar(value=0)
    hue_label = tk.Label(sliders_frame, text="Hue:")
    hue_label.pack(side=tk.LEFT, padx=5)
    hue_slider = tk.Scale(
        sliders_frame,
        from_=-100, to=100, resolution=1,
        orient=tk.HORIZONTAL,
        variable=hue_var,
        command=apply_adjustments
    )
    hue_slider.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

    # Gaussian Blur Slider
    blur_var = tk.DoubleVar(value=0.0)
    blur_label = tk.Label(sliders_frame, text="Gaussian Blur:")
    blur_label.pack(side=tk.LEFT, padx=5)
    blur_slider = tk.Scale(
        sliders_frame,
        from_=0.0, to=10.0, resolution=0.1,
        orient=tk.HORIZONTAL,
        variable=blur_var,
        command=apply_adjustments
    )
    blur_slider.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

    # --- Image Display Area ---
    image_label = tk.Label(root, text="Select an image to start editing.")
    image_label.pack(expand=True, fill="both")

    # Start the Tkinter event loop
    root.mainloop()
