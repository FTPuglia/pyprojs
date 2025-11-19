import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import threading
import time
import os
import csv
from datetime import datetime
from pynput.mouse import Button, Controller, Listener
from pynput.keyboard import Key, Listener as KeyListener, Controller as KeyController

# --- Configuration and Initialization ---

# 1. Set global CTk appearance mode and default theme color
ctk.set_appearance_mode("Dark") 
ctk.set_default_color_theme("green") # Uses a built-in green theme, which we refine below

# Custom Color Definitions (Strictly enforced by CTk)
JADE_GREEN = '#00a86b' # Primary Jade color for active elements
JADE_DARKER = '#008a5c' # Darker Jade for active/hover state
DARK_BG = '#2e2e2e'     # Root window background
WIDGET_BG = '#3c3c3c'   # Frame/Component background
ENTRY_BG = '#4c4c4c'    # Input field background (Fix for readability)
LIGHT_FG = '#ffffff'    # Text color

class MouseSimulatorApp:
    def __init__(self, master):
        self.master = master
        master.title("Advanced Mouse Simulator (CTk)")
        master.resizable(False, False)

        # Initialize pynput controllers
        self.mouse_controller = Controller()
        self.key_controller = Controller()

        # State variables
        self.is_running = False
        self.click_thread = None
        self.macro_recording = False
        self.macro_thread = None
        
        self.mouse_listener = None
        self.last_event_time = None
        self.start_time = None 
        
        self.current_keys = set()
        
        # Start the global keyboard listener in a separate thread
        self.key_listener_thread = threading.Thread(target=self.start_global_listener, daemon=True)
        self.key_listener_thread.start()

        # Settings variables (standard Tkinter variables still work)
        self.lmb_interval = tk.DoubleVar(value=0.02)
        self.rmb_interval = tk.DoubleVar(value=0.5)
        self.click_type = tk.StringVar(value="LMB") # LMB, RMB, BOTH
        
        self.macro_list = []
        
        # UI Setup
        self.setup_ui()

    # --- UI Components and Layout ---
    def setup_ui(self):
        # Main frame (CTkFrame replaces ttk.Frame)
        main_frame = ctk.CTkFrame(self.master, fg_color=DARK_BG)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        # 1. Autoclicker Control Section
        self.create_autoclicker_frame(main_frame).grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        # 2. Macro Recorder Section
        self.create_macro_recorder_frame(main_frame).grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        # 3. Macro List View
        self.create_macro_list_frame(main_frame).grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        
        # 4. Current Cursor Position Status
        self.current_pos_label = ctk.CTkLabel(main_frame, text="Current Cursor: (X: ?, Y: ?)", text_color=LIGHT_FG, 
                                              fg_color=WIDGET_BG, anchor="w", corner_radius=5, height=30)
        self.current_pos_label.grid(row=3, column=0, padx=10, pady=(5, 0), sticky="ew")
        
        # 5. Global Hotkey Status
        self.hotkey_label = ctk.CTkLabel(main_frame, text="Global Kill Switch: Ctrl + Shift + F12", text_color=LIGHT_FG, 
                                         font=ctk.CTkFont(family='Arial', size=9, slant='italic'), 
                                         fg_color=DARK_BG, anchor="w")
        self.hotkey_label.grid(row=4, column=0, padx=10, pady=(0, 5), sticky="ew")
        
        self.update_cursor_position()

    def create_autoclicker_frame(self, parent):
        # CTkFrame used for organization, text set via separate label as CTk doesn't have a direct LabelFrame equivalent
        frame = ctk.CTkFrame(parent, fg_color=WIDGET_BG, border_color=JADE_GREEN, border_width=2)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)

        # LabelFrame Title
        ctk.CTkLabel(frame, text="Autoclicker Controls (Intervals in Seconds)", font=ctk.CTkFont(family='Arial', size=10, weight='bold')).grid(row=0, column=0, columnspan=4, padx=5, pady=(5, 10), sticky="w")
        
        # LMB Interval
        ctk.CTkLabel(frame, text="Left Click Interval:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        # FIX: CTkEntry with explicit colors for readability
        lmb_entry = ctk.CTkEntry(frame, textvariable=self.lmb_interval, width=80, 
                                 fg_color=ENTRY_BG, text_color=LIGHT_FG, border_color=JADE_GREEN)
        lmb_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        # RMB Interval
        ctk.CTkLabel(frame, text="Right Click Interval:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        # FIX: CTkEntry with explicit colors for readability
        rmb_entry = ctk.CTkEntry(frame, textvariable=self.rmb_interval, width=80, 
                                 fg_color=ENTRY_BG, text_color=LIGHT_FG, border_color=JADE_GREEN)
        rmb_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        # Click Type Selection (Using standard Tkinter Radiobuttons as they are simple and easier to manage here)
        ctk.CTkLabel(frame, text="Click Type:").grid(row=1, column=2, padx=10, pady=5, sticky="w")
        tk.Radiobutton(frame, text="Left (LMB)", variable=self.click_type, value="LMB", 
                       bg=WIDGET_BG, fg=LIGHT_FG, selectcolor=WIDGET_BG, indicatoron=0, activebackground=JADE_DARKER).grid(row=1, column=3, padx=5, pady=2, sticky="w")
        tk.Radiobutton(frame, text="Right (RMB)", variable=self.click_type, value="RMB",
                       bg=WIDGET_BG, fg=LIGHT_FG, selectcolor=WIDGET_BG, indicatoron=0, activebackground=JADE_DARKER).grid(row=2, column=3, padx=5, pady=2, sticky="w")
        tk.Radiobutton(frame, text="Both (Alternate)", variable=self.click_type, value="BOTH",
                       bg=WIDGET_BG, fg=LIGHT_FG, selectcolor=WIDGET_BG, indicatoron=0, activebackground=JADE_DARKER).grid(row=3, column=3, padx=5, pady=2, sticky="w")

        # Start/Stop Button (Initial state: Stopped)
        # Using custom color settings on the CTkButton for clear state indication
        self.click_button = ctk.CTkButton(frame, text="Start/Stop Autoclicker (F8)", command=self.toggle_clicker, 
                                          fg_color=JADE_DARKER, hover_color=JADE_GREEN, text_color=LIGHT_FG, 
                                          font=ctk.CTkFont(family='Arial', size=10, weight='bold'))
        self.click_button.grid(row=3, column=0, columnspan=2, padx=5, pady=10, sticky="ew")
        
        return frame

    def create_macro_recorder_frame(self, parent):
        frame = ctk.CTkFrame(parent, fg_color=WIDGET_BG, border_color=JADE_GREEN, border_width=2)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)
        frame.columnconfigure(4, weight=1)
        
        # LabelFrame Title
        ctk.CTkLabel(frame, text="Event-Based Macro Recorder", font=ctk.CTkFont(family='Arial', size=10, weight='bold')).grid(row=0, column=0, columnspan=5, padx=5, pady=(5, 5), sticky="w")
        
        # Instructions
        ctk.CTkLabel(frame, text="Records mouse position/clicks only when a mouse button is pressed or released.", anchor='w').grid(row=1, column=0, columnspan=5, padx=5, pady=2, sticky="w")
        ctk.CTkLabel(frame, text="Toggle recording with the 'F10' key. Macro automatically saves when recording stops.", anchor='w').grid(row=2, column=0, columnspan=5, padx=5, pady=2, sticky="w")
        
        # FIX: CTkButton used with JADE_GREEN for the standard macro buttons
        # The record button now toggles the state, tied to the 'F10' key press
        self.macro_record_button = ctk.CTkButton(frame, text="Start Recording (F10)", command=lambda: self.master.after(0, self.toggle_macro_recording), 
                                                fg_color=JADE_GREEN, hover_color=JADE_DARKER, text_color='#000000') # Dark text on bright jade
        self.macro_record_button.grid(row=3, column=0, padx=5, pady=5, sticky="ew")
        
        play_button = ctk.CTkButton(frame, text="Play Macro", command=self.start_macro_playback, 
                                    fg_color=JADE_GREEN, hover_color=JADE_DARKER, text_color='#000000')
        play_button.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        
        load_button = ctk.CTkButton(frame, text="Load Macro (CSV)", command=self.load_macro_from_csv, 
                                    fg_color=JADE_GREEN, hover_color=JADE_DARKER, text_color='#000000')
        load_button.grid(row=3, column=2, padx=5, pady=5, sticky="ew")
        
        save_button = ctk.CTkButton(frame, text="Save Macro (CSV)", command=self.save_macro_to_csv, 
                                    fg_color=JADE_GREEN, hover_color=JADE_DARKER, text_color='#000000')
        save_button.grid(row=3, column=3, padx=5, pady=5, sticky="ew")

        # Standard button style for Clear Macro (non-jade)
        clear_button = ctk.CTkButton(frame, text="Clear Macro", command=lambda: self.clear_macro(ask_confirm=True))
        clear_button.grid(row=3, column=4, padx=5, pady=5, sticky="ew") 


        return frame

    def create_macro_list_frame(self, parent):
        frame = ctk.CTkFrame(parent, fg_color=WIDGET_BG, border_color=JADE_GREEN, border_width=2)

        # LabelFrame Title
        ctk.CTkLabel(frame, text="Recorded Steps (Time Delay, Action, X, Y, Button)", font=ctk.CTkFont(family='Arial', size=10, weight='bold')).pack(padx=5, pady=(5, 5), anchor="w")

        # Listbox (standard tk widget, styled manually for dark mode, inside the CTk frame)
        # We must use standard tk.Listbox here, as CTk does not provide a wrapper for it.
        self.macro_listbox = tk.Listbox(frame, height=5, width=70, selectmode=tk.SINGLE, font=('Courier New', 9),
                                        bg=ENTRY_BG, fg=LIGHT_FG, selectbackground=JADE_DARKER, selectforeground=LIGHT_FG,
                                        borderwidth=0, highlightthickness=0)
        self.macro_listbox.pack(fill='both', expand=True, padx=10, pady=10)

        return frame

    # --- Autoclicker Logic (Unchanged, relies only on pynput/threading) ---
    def autoclick_loop(self):
        while self.is_running:
            try:
                click_mode = self.click_type.get()
                
                if click_mode == "LMB":
                    self.mouse_controller.click(Button.left)
                    delay = self.lmb_interval.get()
                    time.sleep(delay)
                    
                elif click_mode == "RMB":
                    self.mouse_controller.click(Button.right)
                    delay = self.rmb_interval.get()
                    time.sleep(delay)
                    
                elif click_mode == "BOTH":
                    # Alternating clicks for "Both"
                    self.mouse_controller.click(Button.left)
                    time.sleep(self.lmb_interval.get())
                    if not self.is_running: break

                    self.mouse_controller.click(Button.right)
                    time.sleep(self.rmb_interval.get())

            except ValueError:
                self.stop_clicker()
                self.master.after(0, lambda: messagebox.showerror("Input Error", "Interval must be a valid number."))
            except Exception as e:
                self.stop_clicker()
                self.master.after(0, lambda: messagebox.showerror("Error", f"An error occurred in clicker loop: {e}"))

    def toggle_clicker(self):
        if self.is_running:
            self.stop_clicker()
        else:
            self.start_clicker()

    def start_clicker(self):
        if self.macro_recording:
            messagebox.showwarning("Warning", "Stop macro recording before starting the Autoclicker.")
            return

        try:
            # Validate input before starting
            lmb_delay = self.lmb_interval.get()
            rmb_delay = self.rmb_interval.get()
            if lmb_delay <= 0 or rmb_delay <= 0:
                 raise ValueError("Intervals must be greater than 0.")

            self.is_running = True
            # Update button to indicate running state
            self.click_button.configure(text="Stop Autoclicker (F8)", fg_color=JADE_GREEN, hover_color=JADE_DARKER, text_color=LIGHT_FG)
            
            # Start the click loop in a separate thread
            self.click_thread = threading.Thread(target=self.autoclick_loop, daemon=True)
            self.click_thread.start()
            print(f"Autoclicker started. LMB Interval: {lmb_delay}s, RMB Interval: {rmb_delay}s, Mode: {self.click_type.get()}")

        except ValueError as e:
            messagebox.showerror("Input Error", str(e))

    def stop_clicker(self):
        self.is_running = False
        # Update button to indicate stopped state
        self.click_button.configure(text="Start/Stop Autoclicker (F8)", fg_color=JADE_DARKER, hover_color=JADE_GREEN, text_color=LIGHT_FG)
        if self.click_thread and self.click_thread.is_alive():
            pass
        print("Autoclicker stopped.")

    # --- Macro Logic (Unchanged) ---
    def on_mouse_event(self, x, y, button, pressed):
        """Records mouse clicks (press and release) and their precise timings."""
        if not self.macro_recording:
            return

        current_time = time.time()
        
        if self.last_event_time is None:
            delta_time = 0.0
        else:
            delta_time = current_time - self.last_event_time

        self.last_event_time = current_time

        event_type = 'PRESS' if pressed else 'RELEASE'
        button_name = str(button).split('.')[-1].upper()
        
        record = (delta_time, event_type, x, y, button_name)
        self.macro_list.append(record)
        
        self.master.after(0, self.update_macro_list_display, len(self.macro_list), record)

    def update_macro_list_display(self, step_number, record):
        """Updates the Listbox with the new event record (runs in the main thread)."""
        delta_time, event_type, x, y, button_name = record
        
        display_text = f"Step {step_number: <3}: {event_type: <7} {button_name: <5} @ ({int(x)}, {int(y)}) [Delay: {delta_time:.3f}s]"

        self.macro_listbox.insert(tk.END, display_text)
        self.macro_listbox.see(tk.END)
        
    def load_macro_from_csv(self):
        """Loads macro steps from a user-selected CSV file."""
        if self.macro_recording or self.is_running:
            messagebox.showwarning("Warning", "Stop all functions (Autoclicker/Recording) before loading a macro.")
            return
            
        filename = filedialog.askopenfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Select a Macro CSV File to Load"
        )
        
        if not filename:
            return

        new_macro_list = []
        expected_header = ['Time_Delta_s', 'Event_Type', 'X_Coordinate', 'Y_Coordinate', 'Button_Name']
        
        try:
            with open(filename, 'r', newline='') as csvfile:
                reader = csv.reader(csvfile)
                
                try:
                    header = next(reader)
                except StopIteration:
                    raise ValueError("The selected file is empty.")
                    
                if header != expected_header:
                    raise ValueError("Invalid CSV format. Header does not match expected fields.")

                for i, row in enumerate(reader):
                    if len(row) != 5:
                        raise ValueError(f"Invalid row length at line {i+2}: Expected 5 fields, got {len(row)}.")
                        
                    delta_time = float(row[0])
                    event_type = row[1].upper()
                    x = int(row[2])
                    y = int(row[3])
                    button_name = row[4].upper()
                    
                    if event_type not in ['PRESS', 'RELEASE']:
                        raise ValueError(f"Invalid Event_Type '{event_type}' at line {i+2}.")

                    new_macro_list.append((delta_time, event_type, x, y, button_name))
            
            self.clear_macro(ask_confirm=False) 
            self.macro_list = new_macro_list
            
            self.macro_listbox.delete(0, tk.END)
            for i, record in enumerate(self.macro_list):
                self.update_macro_list_display(i + 1, record) 
            
            print(f"Macro loaded successfully from: {filename}. Total events: {len(self.macro_list)}")
            messagebox.showinfo("Load Successful", f"Macro successfully loaded from:\n{os.path.basename(filename)}")
            
        except FileNotFoundError:
            messagebox.showerror("Load Error", "File not found.")
        except ValueError as e:
            messagebox.showerror("Load Error", str(e))
        except Exception as e:
            messagebox.showerror("Load Error", f"An unexpected error occurred during file processing: {e}")

    def save_macro_to_csv(self):
        """Saves the recorded macro steps to a CSV file in the script's directory."""
        if not self.macro_list:
            messagebox.showwarning("Save Macro", "No events recorded to save.")
            return

        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
        except NameError:
            script_dir = os.getcwd() 
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(script_dir, f"macro_events_{timestamp}.csv")
        
        fieldnames = ['Time_Delta_s', 'Event_Type', 'X_Coordinate', 'Y_Coordinate', 'Button_Name']

        try:
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                writer.writerow(fieldnames)
                
                for record in self.macro_list:
                    writer.writerow([f"{record[0]:.6f}", record[1], int(record[2]), int(record[3]), record[4]])

            print(f"Macro successfully saved to: {filename}")
            messagebox.showinfo("Save Successful", f"Macro successfully saved to:\n{filename}")
            return True
        
        except Exception as e:
            error_msg = f"Failed to save macro to CSV: {e}"
            print(error_msg)
            messagebox.showerror("Save Error", error_msg)
            return False


    def clear_macro(self, ask_confirm=True):
        if self.macro_recording:
            messagebox.showwarning("Warning", "Stop recording before clearing the macro.")
            return

        perform_clear = True
        if ask_confirm:
            perform_clear = messagebox.askyesno("Clear Macro", "Are you sure you want to clear all recorded steps?")
        
        if perform_clear:
            self.macro_list = []
            self.macro_listbox.delete(0, tk.END)
            print("Macro cleared.")

    def toggle_macro_recording(self):
        """Toggles the macro recording state, triggered by 'F10' or GUI button."""
        if self.is_running:
             messagebox.showwarning("Warning", "Stop the Autoclicker before recording a macro.")
             return
             
        if self.macro_recording:
            # Stop recording
            self.macro_recording = False
            # Update button to indicate stopped state (Jade color)
            self.macro_record_button.configure(text="Start Recording (F10)", fg_color=JADE_GREEN, text_color='#000000') 
            
            if self.mouse_listener:
                self.mouse_listener.stop()
                self.mouse_listener = None
                self.last_event_time = None
                self.start_time = None
            
            print(f"Macro recording stopped. Recorded {len(self.macro_list)} events.")

            if self.macro_list:
                self.master.after(0, self.save_macro_to_csv)

        else:
            # Start recording
            if len(self.macro_list) > 0 and messagebox.askyesno("Macro Exists", "Do you want to clear the existing macro before starting a new one?"):
                 self.clear_macro(ask_confirm=False)
            
            self.macro_recording = True
            # Update button to indicate running state (Darker Jade color)
            self.macro_record_button.configure(text="Stop Recording (F10)", fg_color=JADE_DARKER, text_color=LIGHT_FG) 
            
            self.last_event_time = None
            self.start_time = time.time()
            
            self.mouse_listener = Listener(on_click=self.on_mouse_event)
            self.macro_thread = threading.Thread(target=self.mouse_listener.start, daemon=True)
            self.macro_thread.start()
            print("Macro recording started (Event-Driven).")

    def macro_playback_loop(self):
        try:
            if not self.macro_list:
                self.master.after(0, lambda: messagebox.showinfo("Playback Info", "The macro list is empty. Please record events first."))
                return

            self.master.after(0, lambda: messagebox.showinfo("Playback Start", "Macro starting. Control is ceded until finished."))
            
            for i, record in enumerate(self.macro_list):
                delta_time, event_type, x, y, button_name = record
                
                time.sleep(delta_time)
                
                self.mouse_controller.position = (x, y)
                
                if button_name == 'LEFT':
                    button = Button.left
                elif button_name == 'RIGHT':
                    button = Button.right
                else:
                    continue

                if event_type == 'PRESS':
                    self.mouse_controller.press(button)
                elif event_type == 'RELEASE':
                    self.mouse_controller.release(button)


            self.master.after(0, lambda: messagebox.showinfo("Playback Complete", "Macro playback finished."))

        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("Macro Error", f"An error occurred during macro playback: {e}"))

    def start_macro_playback(self):
        if self.macro_recording or self.is_running:
            messagebox.showwarning("Warning", "Stop any active function (Autoclicker/Recording) before playback.")
            return
            
        playback_thread = threading.Thread(target=self.macro_playback_loop, daemon=True)
        playback_thread.start()

    # --- Utility and Cleanup ---
    def update_cursor_position(self):
        """Continuously updates the label with the current mouse position."""
        try:
            x, y = self.mouse_controller.position
            self.current_pos_label.configure(text=f"Current Cursor: (X: {int(x)}, Y: {int(y)}) - Pixel Coordinates")
        except Exception:
            self.current_pos_label.configure(text="Current Cursor: (X: ?, Y: ?) - Error retrieving position")

        self.master.after(100, self.update_cursor_position)

    def start_global_listener(self):
        """Initializes and runs the global keyboard listener for the kill switch and macro toggle."""
        def on_press_global(key):
            try:
                self.current_keys.add(key)
                
                is_ctrl_down = Key.ctrl_l in self.current_keys or Key.ctrl_r in self.current_keys
                is_shift_down = Key.shift_l in self.current_keys or Key.shift_r in self.current_keys

                if key == Key.f12 and is_ctrl_down and is_shift_down:
                    print("\n[SYSTEM] Kill Combo (Ctrl+Shift+F12) pressed. Exiting program.")
                    self.master.after(0, self.graceful_exit)
                    return
                
                if key == Key.f8:
                    print("\n[SYSTEM] F8 pressed. Toggling Autoclicker state.")
                    self.master.after(0, self.toggle_clicker)
                    return

                if key == Key.f10:
                    print("\n[SYSTEM] F10 pressed. Toggling Macro Recording state.")
                    self.master.after(0, self.toggle_macro_recording)
                    return

            except Exception:
                pass 

        def on_release_global(key):
            try:
                self.current_keys.discard(key)
            except KeyError:
                pass 

        with KeyListener(on_press=on_press_global, on_release=on_release_global) as listener:
            listener.join()

    def graceful_exit(self):
        """Stops threads and closes the application safely."""
        self.stop_clicker()
        
        if self.mouse_listener:
            try:
                self.mouse_listener.stop()
            except Exception:
                pass 

        if self.macro_recording:
            self.macro_recording = False
            
        self.master.quit()
        os._exit(0)


def main():
    # Crucial change: Use ctk.CTk() instead of tk.Tk()
    root = ctk.CTk()
    app = MouseSimulatorApp(root)
    
    root.protocol("WM_DELETE_WINDOW", app.graceful_exit)
    root.mainloop()

if __name__ == "__main__":
    main()
