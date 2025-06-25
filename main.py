import network
import machine
import time
import json
import requests

from ota import OTAUpdater

from machine import I2C, Pin
from i2c_lcd import I2cLcd

# LCD Configuration
I2C_ADDR = 0x27
I2C_NUM_ROWS = 2
I2C_NUM_COLS = 16

# Initialize I2C and LCD
i2c = I2C(0, scl=Pin(5), sda=Pin(4), freq=400000)
lcd = I2cLcd(i2c, I2C_ADDR, I2C_NUM_ROWS, I2C_NUM_COLS)

# Display welcome message
lcd.move_to(0, 0)
lcd.putstr("Vacuum Output")

# Load and display version from JSON file
try:
    import json
    with open('version.json', 'r') as f:
        version_data = json.load(f)
        version = str(version_data.get('version', 'Unknown'))
    lcd.move_to(1, 0)
    lcd.putstr(f"Version: {version}")
except Exception as e:
    lcd.move_to(1, 0)
    lcd.putstr("Version: Unknown")

time.sleep(2)
# Clear LCD for main operation
lcd.move_to(0, 0)
lcd.putstr("                ")
lcd.move_to(1, 0)
lcd.putstr("                ")

# WiFi Configuration
SSID = "SYS-Horizon"
PASSWORD = "9078@horiz"

# 4x4 Keypad Configuration
COL_PINS = [6, 7, 8, 9]
ROW_PINS = [10, 11, 12, 13]
KEYS = [
    ['1', '4', '7', '*'],
    ['2', '5', '8', '0'],
    ['3', '6', '9', '#'],
    ['A', 'B', 'C', 'D']
]
rows = [machine.Pin(pin, machine.Pin.OUT) for pin in ROW_PINS]
cols = [machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_UP) for pin in COL_PINS]

# Initialize WiFi
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# Initialize UART for weight sensor communication
uart = machine.UART(0, baudrate=9600, tx=machine.Pin(0), rx=machine.Pin(1))

last_status = None

def connect_wifi():
    """Connect to WiFi network"""
    if not wlan.isconnected():
        wlan.connect(SSID, PASSWORD)
        for _ in range(20):
            if wlan.isconnected():
                break
            time.sleep(0.5)
    update_wifi_status(force=True)

def update_wifi_status(force=False):
    """Update WiFi connection status on LCD"""
    global last_status
    status = wlan.isconnected()

    # Auto-reconnect if disconnected
    if not status:
        wlan.connect(SSID, PASSWORD)
        retries = 10
        while not wlan.isconnected() and retries > 0:
            lcd.move_to(1, 0)
            lcd.putstr("WiFi: Reconnecting")
            time.sleep(0.5)
            retries -= 1

    status = wlan.isconnected()
    if force or status != last_status:
        lcd.move_to(1, 0)
        lcd.putstr("                ")
        if status:
            lcd.move_to(1, 0)
            lcd.putstr("WiFi: Connected")
        else:
            lcd.move_to(1, 0)
            lcd.putstr("WiFi: Disconn.")
        last_status = status

def scan_keypad():
    """Scan 4x4 keypad and return pressed key"""
    for r_idx, row in enumerate(rows):
        # Set all rows high
        for r in rows:
            r.value(1)
        # Set current row low
        row.value(0)
        # Check each column
        for c_idx, col in enumerate(cols):
            if col.value() == 0:
                time.sleep_ms(20)  # Debounce
                if col.value() == 0:
                    return KEYS[r_idx][c_idx]
    return None

def flush_uart():
    """Clear UART buffer"""
    while uart.any():
        uart.read()

def receive_number():
    """Receive weight data from UART sensor"""
    flush_uart()
    buffer = b""
    while True:
        if uart.any():
            char = uart.read(1)
            if char == b'\r':  # End of transmission
                break
            buffer += char
        time.sleep_ms(10)
    
    # Parse weight from format "+ 1234 k" to "1234"
    whole_weight = buffer.decode().strip()
    indexplus = whole_weight.find('+')
    indexK = whole_weight.find('k')
    weight = whole_weight[indexplus+1:indexK]
    weight = weight.replace(' ', '')
    return weight

def extract_between_plus_and_k(text = "+ k"):
    """Extract value between '+' and 'k' characters"""
    try:
        start = text.index('+') + 1
        end = text.index('k', start)
        return text[start:end].strip()
    except ValueError:
        return ''

def trigger_ota_update():
    """Handle OTA update process with password protection"""
    time.sleep(0.5)
    lcd.move_to(0, 0)
    lcd.putstr("                ")
    lcd.move_to(0, 0)
    lcd.putstr("Enter Password:")
    lcd.move_to(0, 15)
    lcd.putstr("*")
    
    password_buffer = ""
    last_key = None
    
    while True:
        update_wifi_status()
        key = scan_keypad()
        
        if key and key != last_key:
            if key == '#':  # Enter key
                if password_buffer == "1234":  # OTA password
                    lcd.move_to(0, 0)
                    lcd.putstr("                ")
                    lcd.move_to(0, 0)
                    lcd.putstr("Starting OTA...")
                    try:
                        firmware_url = "https://github.com/mahmoudrizkk/Vacuum-Output/"
                        ota_updater = OTAUpdater(SSID, PASSWORD, firmware_url, "main.py")
                        ota_updater.download_and_install_update_if_available()
                        lcd.move_to(0, 0)
                        lcd.putstr("                ")
                        lcd.move_to(0, 0)
                        lcd.putstr("OTA Success")
                        time.sleep(3)
                    except Exception as e:
                        lcd.move_to(0, 0)
                        lcd.putstr("                ")
                        lcd.move_to(0, 0)
                        lcd.putstr("OTA Failed")
                        lcd.move_to(0, 10)
                        lcd.putstr(str(e)[:6])
                        time.sleep(3)
                    return
                else:
                    lcd.move_to(0, 0)
                    lcd.putstr("                ")
                    lcd.move_to(0, 0)
                    lcd.putstr("Wrong Password!")
                    time.sleep(2)
                    password_buffer = ""
                    lcd.move_to(0, 0)
                    lcd.putstr("                ")
                    lcd.move_to(0, 0)
                    lcd.putstr("Enter Password:")
                    lcd.move_to(0, 15)
                    lcd.putstr("*")
            elif key == '*':  # Cancel key
                lcd.move_to(0, 0)
                lcd.putstr("                ")
                lcd.move_to(0, 0)
                lcd.putstr("Update Cancelled")
                time.sleep(2)
                lcd.move_to(0, 0)
                lcd.putstr("                ")
                lcd.move_to(0, 0)
                lcd.putstr("Enter Type:")
                lcd.move_to(1, 0)
                lcd.putstr("Press # to confirm")
                return
            elif key in '0123456789ABC':  # Password digits
                password_buffer += key
                lcd.move_to(0, 0)
                lcd.putstr("                ")
                lcd.move_to(0, 0)
                lcd.putstr("Enter Password:")
                lcd.move_to(0, 15)
                lcd.putstr("*" * min(len(password_buffer), 1))
            last_key = key
        elif not key:
            last_key = None
        
        time.sleep_ms(100)

def get_last_barcode(selected_type):
    """Fetch last barcode from API for selected type (1=Liver, 2=Heart)"""
    url = f"http://shatat-ue.runasp.net/api/Devices/LastBarcodeForLiverAndHeart?type={selected_type}"
    
    try:
        update_wifi_status()
        
        lcd.move_to(0, 0)
        lcd.putstr("                ")
        lcd.move_to(0, 0)
        lcd.putstr("Getting barcode...")

        response = requests.get(url, timeout=10)
        response_text = response.text
        response.close()

        try:
            response_json = json.loads(response_text)
            barcode = str(response_json.get('message', ''))
            
            if barcode:
                lcd.move_to(0, 0)
                lcd.putstr("                ")
                lcd.move_to(0, 0)
                lcd.putstr("Barcode:")
                lcd.move_to(0, 8)
                lcd.putstr(barcode[:8])
                
                time.sleep(3)
                lcd.move_to(0, 0)
                lcd.putstr("                ")
                lcd.move_to(0, 0)
                lcd.putstr("Barcode received!")
            else:
                lcd.move_to(0, 0)
                lcd.putstr("                ")
                lcd.move_to(0, 0)
                lcd.putstr("No barcode found")
                
        except json.JSONDecodeError:
            lcd.move_to(0, 0)
            lcd.putstr("                ")
            lcd.move_to(0, 0)
            lcd.putstr("JSON Error")
        except Exception as e:
            lcd.move_to(0, 0)
            lcd.putstr("                ")
            lcd.move_to(0, 0)
            lcd.putstr("Error")

        time.sleep(2)
        lcd.move_to(0, 0)
        lcd.putstr("                ")

    except Exception as e:
        lcd.move_to(0, 0)
        lcd.putstr("                ")
        lcd.move_to(0, 0)
        lcd.putstr("Get failed:")
        lcd.move_to(0, 11)
        lcd.putstr(str(e)[:5])
        time.sleep(2)

def trigger_barcode_request():
    """Handle B button press - request barcode for selected type"""
    lcd.move_to(0, 0)
    lcd.putstr("                ")
    lcd.move_to(0, 0)
    lcd.putstr("Get Last Barcode")
    lcd.move_to(1, 0)
    lcd.putstr("Select: 1:L 2:H")
    
    selected_type = None
    last_key = None
    
    while selected_type is None:
        update_wifi_status()
        key = scan_keypad()
        
        if key and key != last_key:
            if key == '1':
                selected_type = 1  # Liver
            elif key == '2':
                selected_type = 2  # Heart
            elif key == '#':  # Cancel
                lcd.move_to(0, 0)
                lcd.putstr("                ")
                lcd.move_to(1, 0)
                lcd.putstr("                ")
                lcd.move_to(0, 0)
                lcd.putstr("Cancelled")
                time.sleep(2)
                return
            last_key = key
        elif not key:
            last_key = None
        
        time.sleep_ms(100)
    
    if selected_type:
        lcd.move_to(0, 0)
        lcd.putstr("                ")
        lcd.move_to(1, 0)
        lcd.putstr("                ")
        lcd.move_to(0, 0)
        lcd.putstr("Type:")
        lcd.move_to(0, 5)
        lcd.putstr("Liver" if selected_type == 1 else "Heart")
        time.sleep(1)
        
        get_last_barcode(selected_type)

def send_number(weight, cuttingId):
    # http://shatat-ue.runasp.net/api/Devices/PreCuttingItem?weight=1&cuttingId=1&machineid=1
    url = f"http://shatat-ue.runasp.net/api/Devices/PreCuttingItem?weight={weight}&cuttingId={cuttingId}&machineid=1"
    
    try:
        update_wifi_status()
        
        # Clear LCD first line
        lcd.move_to(0, 0)
        lcd.putstr(" " * 16)
        
        # Show sending info
        lcd.move_to(0, 0)
        lcd.putstr(f"Sending:{weight}")

        # Send the POST request
        response = requests.get(url)
        text = response.text
        response.close()

        # Clear LCD and display response
        lcd.move_to(0, 0)
        lcd.putstr(" " * 16)
        lcd.move_to(0, 0)
        lcd.putstr("R:" + text[:16])
        time.sleep(3)

    except Exception as e:
        # Display error message
        lcd.move_to(0, 0)
        lcd.putstr(" " * 16)
        lcd.move_to(0, 0)
        lcd.putstr("failed:" + str(e)[:16])
        time.sleep(2)

def main():
    """Main application loop"""
    connect_wifi()

    while True:
        number_buffer = ""
        selected_type = None
        last_key = None

        # Step 1: Type Selection
        update_wifi_status(force=True)
        lcd.move_to(0, 0)
        lcd.putstr("                ")
        lcd.move_to(0, 0)
        lcd.putstr("Enter Type:")
        lcd.move_to(1, 0)
        lcd.putstr("Press # to confirm")

        # Wait for type input and confirmation
        while selected_type is None:
            update_wifi_status()
            key = scan_keypad()
            
            if key and key != last_key:
                if key == '#':  # Enter key to confirm
                    if number_buffer:
                        selected_type = int(number_buffer)
                        lcd.move_to(0, 0)
                        lcd.putstr("                ")
                        lcd.move_to(0, 0)
                        lcd.putstr("Type:")
                        lcd.move_to(0, 5)
                        lcd.putstr(str(selected_type))
                        time.sleep(1)
                    else:
                        lcd.move_to(0, 0)
                        lcd.putstr("                ")
                        lcd.move_to(0, 0)
                        lcd.putstr("Enter a number!")
                        time.sleep(1)
                        lcd.move_to(0, 0)
                        lcd.putstr("                ")
                        lcd.move_to(0, 0)
                        lcd.putstr("Enter Type:")
                        lcd.move_to(1, 0)
                        lcd.putstr("Press # to confirm")
                elif key == 'D':  # Backspace
                    number_buffer = number_buffer[:-1]
                    lcd.move_to(0, 0)
                    lcd.putstr("                ")
                    lcd.move_to(0, 0)
                    lcd.putstr("Type:")
                    lcd.move_to(0, 5)
                    lcd.putstr(number_buffer)
                    lcd.move_to(1, 0)
                    lcd.putstr("Press # to confirm")
                elif key == '*':
                    trigger_ota_update()  # 🚀 Trigger OTA when * is pressed
                elif key in '0123456789':  # Number input
                    number_buffer += key
                    lcd.move_to(0, 0)
                    lcd.putstr("                ")
                    lcd.move_to(0, 0)
                    lcd.putstr("Type:")
                    lcd.move_to(0, 5)
                    lcd.putstr(number_buffer)
                    lcd.move_to(1, 0)
                    lcd.putstr("Press # to confirm")
                last_key = key
            elif not key:
                last_key = None
            
            time.sleep_ms(100)

        # Step 2: Display Selection
        lcd.move_to(0, 0)
        lcd.putstr("                ")
        lcd.move_to(0, 0)
        lcd.putstr("Selected Type:")
        lcd.move_to(0, 14)
        lcd.putstr(str(selected_type))
        time.sleep(1)
        
        # Step 3: Wait for Weight
        lcd.move_to(0, 0)
        lcd.putstr("                ")
        lcd.move_to(0, 0)
        lcd.putstr("Waiting weight...")
        update_wifi_status()

        # Step 4: Receive Weight from Sensor
        received_weight = receive_number()

        # Step 5: Display Weight
        lcd.move_to(0, 0)
        lcd.putstr("                ")
        lcd.move_to(0, 0)
        lcd.putstr("Weight:")
        lcd.move_to(0, 7)
        lcd.putstr(received_weight[:9])
        update_wifi_status()
        time.sleep(1)

        # Step 6: Send to API
        try:
            send_number(received_weight, selected_type)

        except Exception as e:
            lcd.move_to(0, 0)
            lcd.putstr("                ")
            lcd.move_to(0, 0)
            lcd.putstr("Error:")
            lcd.move_to(0, 6)
            lcd.putstr(str(e)[:10])

        update_wifi_status()
        time.sleep(3)

        # Step 8: Success Message and Restart
        lcd.move_to(0, 0)
        lcd.putstr("                ")
        lcd.move_to(0, 0)
        lcd.putstr("Done!")
        update_wifi_status()
        time.sleep(2)

def main2():
    """Alternative main function for testing UART only"""
    while True:
        whole_weight = receive_number()
        indexplus = whole_weight.find('+')
        indexK = whole_weight.find('k')
        weight = whole_weight[indexplus+1:indexK+2]
        weight = ""

if __name__ == "__main__":
    main()