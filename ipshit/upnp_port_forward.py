import socket
import sys
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext

# --- Library Check and Placeholder Setup ---
UPnP = None
try:
    import miniupnpc
    UPnP = miniupnpc.UPnP
    UPnP_AVAILABLE = True
except ImportError:
    UPnP_AVAILABLE = False
    
# Global constant for the main model used in the GUI
MODEL_NAME = "gemini-2.5-flash-preview-05-20" 
# NOTE: The LLM model is not used in this networking script, but this placeholder 
# maintains the required code structure for a single-file application.

class UPnPPortForwardingApp:
    """A GUI application for managing UPnP port forwarding via tkinter."""

    def __init__(self, master):
        self.master = master
        master.title("UPnP Port Forwarding Tool")
        master.resizable(False, False)
        
        # Internal state
        self.protocol_var = tk.StringVar(value='both')
        self.port_entry_var = tk.StringVar()
        self.local_ip = self._get_local_ip()
        self.external_ip = "N/A"
        self.upnp_instance = None
        
        # --- UI Setup ---
        self._create_widgets()
        
        if not UPnP_AVAILABLE:
            self._log_status("CRITICAL ERROR: 'miniupnpc' library is not installed or failed to load. Port forwarding will not work.", is_error=True)
            self._log_status("Please run: pip install miniupnpc", is_error=True)
        else:
            self._log_status("UPnP library loaded. Ready to discover router.", is_success=True)

    # --- Utility Functions ---

    def _get_local_ip(self):
        """Attempts to find the local IP address of the machine."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 1))
            local_ip = s.getsockname()[0]
        except Exception:
            local_ip = '127.0.0.1'
        finally:
            s.close()
        return local_ip
        
    def _log_status(self, message, is_error=False, is_success=False):
        """Updates the log text widget with a timestamped message."""
        timestamp = time.strftime("[%H:%M:%S]")
        
        if is_error:
            tag = "error"
            message = f"{timestamp} [ERROR] {message}"
        elif is_success:
            tag = "success"
            message = f"{timestamp} [SUCCESS] {message}"
        else:
            tag = "info"
            message = f"{timestamp} [INFO] {message}"
            
        self.log_text.insert(tk.END, message + "\n", tag)
        self.log_text.see(tk.END) # Scroll to the bottom
        self.master.update_idletasks() # Force update GUI

    def _run_task_in_thread(self, target_func, *args):
        """Runs a blocking task in a separate thread to prevent GUI freezing."""
        if not UPnP_AVAILABLE:
            self._log_status("Cannot run task: miniupnpc library is missing.", is_error=True)
            return
            
        self._log_status("Starting network operation in background thread...")
        self.forward_button.config(state=tk.DISABLED)
        self.delete_button.config(state=tk.DISABLED)
        
        def run_and_re_enable():
            try:
                target_func(*args)
            finally:
                # Re-enable buttons on thread completion, ensuring it runs on main thread
                self.master.after(100, lambda: self.forward_button.config(state=tk.NORMAL))
                self.master.after(100, lambda: self.delete_button.config(state=tk.NORMAL))
                self._log_status("Operation finished. Buttons re-enabled.")

        thread = threading.Thread(target=run_and_re_enable)
        thread.daemon = True
        thread.start()

    # --- Core UPnP Logic (Updates Log directly) ---
    
    def _initialize_upnp(self):
        """Initializes the UPnP instance, discovers devices, and gets IPs."""
        self._log_status("Discovering UPnP devices...")
        try:
            self.upnp_instance = UPnP()
            self.upnp_instance.discoverdelay = 200
            num_devices = self.upnp_instance.discover()
            
            if num_devices == 0:
                self._log_status("❌ No UPnP devices found. Router may not support UPnP.", is_error=True)
                return False

            self.upnp_instance.selectigd()
            self.external_ip = self.upnp_instance.externalipaddress()
            self._log_status(f"✅ UPnP Device found. Local IP: {self.local_ip} | External IP: {self.external_ip}", is_success=True)
            return True
        
        except Exception as e:
            self._log_status(f"❌ Failed to initialize UPnP or select IGD: {e}", is_error=True)
            self.upnp_instance = None
            return False

    def _perform_port_check(self, port):
        """Checks if a local port is in use."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(('0.0.0.0', port))
            s.close()
            self._log_status(f"Local Port Check: Port {port} is available.")
            return False
        except socket.error as e:
            if e.errno in (98, 48, 10048): 
                self._log_status(f"Local Port Check: Port {port} is IN USE locally. External connection requires an app to be running on it.", is_error=True)
                return True
            else:
                self._log_status(f"Error checking local port {port}: {e}", is_error=True)
                return True

    def _attempt_forward(self, port, protocol):
        """Internal worker function to add port mappings."""
        if not self._initialize_upnp():
            return

        self._perform_port_check(port)

        protocols_to_map = []
        if protocol in ('tcp', 'both'): protocols_to_map.append('TCP')
        if protocol in ('udp', 'both'): protocols_to_map.append('UDP')
        
        total_success = 0
        
        for p in protocols_to_map:
            try:
                success = self.upnp_instance.addportmapping(
                    port, p, self.local_ip, port, 
                    f'GUI_P{port}_{p}', '', 0
                )
                
                if success:
                    self._log_status(f"✅ SUCCESS: {p} Port {port} forwarded.", is_success=True)
                    total_success += 1
                else:
                    # Check if the port already exists (getspecificportmapping)
                    desc = self.upnp_instance.getspecificportmapping(port, p)[5]
                    if desc:
                        self._log_status(f"⚠️ WARNING: {p} Port {port} already exists: '{desc}'", is_error=True)
                    else:
                        self._log_status(f"❌ FAILED: Router refused {p} mapping for port {port}.", is_error=True)

            except Exception as e:
                self._log_status(f"Critical error during {p} mapping: {e}", is_error=True)
                
        if total_success > 0:
            self._log_status("\n--- Verification Needed ---", is_success=True)
            self._log_status(f"1. Run your app on local port {port}.")
            self._log_status(f"2. Check public access using External IP: {self.external_ip} and Port: {port}")
            self._log_status("   (Use an online 'external port checker' tool to verify.)", is_success=True)
        else:
             self._log_status("❌ FATAL: No ports were successfully forwarded.", is_error=True)

    def _attempt_delete(self, port, protocol):
        """Internal worker function to delete port mappings."""
        if not self._initialize_upnp():
            return
        
        protocols_to_delete = []
        if protocol in ('tcp', 'both'): protocols_to_delete.append('TCP')
        if protocol in ('udp', 'both'): protocols_to_delete.append('UDP')

        for p in protocols_to_delete:
            try:
                self.upnp_instance.deleteportmapping(port, p)
                self._log_status(f"✅ SUCCESS: Deleted {p} mapping for port {port}.", is_success=True)
            except Exception as e:
                self._log_status(f"⚠️ WARNING: Failed to delete {p} mapping for port {port}. May not have existed: {e}", is_error=True)

    # --- Button Handlers ---

    def _validate_input(self):
        """Validates port number input."""
        try:
            port = int(self.port_entry_var.get())
            if not (1 <= port <= 65535):
                raise ValueError("Port must be between 1 and 65535.")
            return port
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please enter a valid port number.\n{e}")
            return None

    def handle_forward(self):
        port = self._validate_input()
        if port is not None:
            protocol = self.protocol_var.get()
            self._log_status(f"\n--- REQUEST: Forwarding Port {port} ({protocol.upper()}) ---")
            self._run_task_in_thread(self._attempt_forward, port, protocol)

    def handle_delete(self):
        port = self._validate_input()
        if port is not None:
            protocol = self.protocol_var.get()
            self._log_status(f"\n--- REQUEST: Deleting Port {port} ({protocol.upper()}) ---")
            self._run_task_in_thread(self._attempt_delete, port, protocol)

    # --- GUI Layout ---

    def _create_widgets(self):
        # 1. Control Frame
        control_frame = tk.Frame(self.master, padx=10, pady=10)
        control_frame.pack(fill='x')

        # Port Input
        tk.Label(control_frame, text="Target Port (1-65535):").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        port_entry = tk.Entry(control_frame, textvariable=self.port_entry_var, width=10, justify='center')
        port_entry.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
        port_entry.insert(0, "8080")

        # Protocol Selection
        tk.Label(control_frame, text="Protocol:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        
        protocol_frame = tk.Frame(control_frame)
        protocol_frame.grid(row=1, column=1, sticky='ew', padx=5, pady=5)
        
        tk.Radiobutton(protocol_frame, text="TCP", variable=self.protocol_var, value='tcp').pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(protocol_frame, text="UDP", variable=self.protocol_var, value='udp').pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(protocol_frame, text="Both", variable=self.protocol_var, value='both').pack(side=tk.LEFT, padx=5)

        # Action Buttons
        self.forward_button = tk.Button(control_frame, text="Forward Port", command=self.handle_forward, 
                                        bg="#4CAF50", fg="white", activebackground="#6aa84f", relief=tk.RAISED, bd=3)
        self.forward_button.grid(row=2, column=0, sticky='ew', padx=5, pady=10)
        
        self.delete_button = tk.Button(control_frame, text="Delete Mapping", command=self.handle_delete, 
                                       bg="#F44336", fg="white", activebackground="#d64035", relief=tk.RAISED, bd=3)
        self.delete_button.grid(row=2, column=1, sticky='ew', padx=5, pady=10)
        
        # 2. Status/Log Frame
        log_label = tk.Label(self.master, text="--- Status Log ---", font=('Arial', 10, 'bold'))
        log_label.pack(fill='x', padx=10, pady=(5, 0))

        self.log_text = scrolledtext.ScrolledText(self.master, width=50, height=15, state='normal', font=('Consolas', 10), wrap=tk.WORD)
        self.log_text.pack(padx=10, pady=10, fill='both', expand=True)

        # Configure tags for colored logging
        self.log_text.tag_config('error', foreground='red')
        self.log_text.tag_config('success', foreground='green')
        self.log_text.tag_config('info', foreground='blue')

if __name__ == '__main__':
    import time # Ensure time is imported for logging timestamp

    root = tk.Tk()
    app = UPnPPortForwardingApp(root)
    root.mainloop()
