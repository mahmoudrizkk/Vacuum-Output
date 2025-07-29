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
#
#  ----------------
# |Vacuum Output   |
# |                |
#  ----------------
lcd.move_to(0, 0)
lcd.putstr("Vacuum Output")

# Load and display version from JSON file
try:
    import json
    with open('version.json', 'r') as f:
        version_data = json.load(f)
        version = str(version_data.get('version', 'Unknown'))
    #
    #  ----------------
    # |                |
    # |Version: <ver>  |
    #  ----------------
    lcd.move_to(1, 0)
    lcd.putstr(f"Version: {version}")
except Exception as e:
    #
    #  ----------------
    # |                |
    # |Version: Unknown|
    #  ----------------
    lcd.move_to(1, 0)
    lcd.putstr("Version: Unknown")

time.sleep(2)
# Clear LCD for main operation
#
#  ----------------
# |                |
# |                |
#  ----------------
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
            #
            #  ----------------
            # |                |
            # |WiFi: Reconnect.|
            #  ----------------
            lcd.move_to(1, 0)
            lcd.putstr("WiFi: Reconnect.")
            time.sleep(0.5)
            retries -= 1

    status = wlan.isconnected()
    if force or status != last_status:
        #
        #  ----------------
        # |                |
        # |WiFi: Connected |
        #  ----------------
        # or
        #  ----------------
        # |                |
        # |WiFi: Disconn.  |
        #  ----------------
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

# For this data : + 1234 k
# def receive_number():
#     """Receive weight data from UART sensor"""
#     flush_uart()
#     buffer = b""
#     while True:
#         if uart.any():
#             char = uart.read(1)
#             if char == b'\r':  # End of transmission
#                 break
#             buffer += char
#         time.sleep_ms(10)
    
#     # Parse weight from format "+ 1234 k" to "1234"
#     whole_weight = buffer.decode().strip()
#     indexplus = whole_weight.find('+')
#     indexK = whole_weight.find('k')
#     weight = whole_weight[indexplus+1:indexK]
#     weight = weight.replace(' ', '')
#     return weight

    # For this data : ST,GS,       0.00,kg
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
    
    # Parse weight from format "ST,GS,       0.00,kg" to extract the number
    whole_weight = buffer.decode().strip()
    
    # Split by comma and get the third element (index 2) which contains the weight
    parts = whole_weight.split(',')
    if len(parts) >= 3:
        weight_part = parts[2].strip()  # Remove whitespace
        # Extract only the numeric part (remove 'kg', '+', ' ' if present)
        weight = weight_part.replace('kg', '').replace('+', '').replace(' ', '').strip()
        return weight
    else:
        return "0.00"  # Default if parsing fails

def extract_between_plus_and_k(text = "+ k"):
    """Extract value between '+' and 'k' characters"""
    try:
        start = text.index('+') + 1
        end = text.index('k', start)
        return text[start:end].strip()
    except ValueError:
        return ''

# firmware_url = "https://github.com/mahmoudrizkk/Vacuum-Output/"

def trigger_ota_update():
    """Handle OTA update process with password protection"""
    time.sleep(0.5)
    lcd.move_to(0, 0)
    lcd.putstr("                ")
    lcd.move_to(0, 0)
    lcd.putstr("Enter Password:")
    lcd.move_to(1, 0)
    lcd.putstr("                ")  # Clear the second line
    lcd.move_to(1, 0)
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
                    lcd.move_to(1, 0)
                    lcd.putstr("                ")
                    lcd.move_to(1, 0)
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
                lcd.move_to(1, 0)
                lcd.putstr("                ")
                lcd.move_to(1, 0)
                lcd.putstr("*" * min(len(password_buffer), 1))
            last_key = key
        elif not key:
            last_key = None
        
        time.sleep_ms(100)

def send_pre_cutting_item(status, number_of_parneka, type_id, weight_of_parneka, weight, orderIndex, machine_id=1):
    # Devices/PreCuttingItem?Status=1&NumberOfParneka=1&TypeId=1&WeightOfParneka=15&Weight=20&orderIndex=1&MachineId=1
    url = (
        "http://shatat-ue.runasp.net/api/Devices/PreCuttingItem"
        f"?Status={status}"
        f"&NumberOfParneka={number_of_parneka}"
        f"&TypeId={type_id}"
        f"&WeightOfParneka={weight_of_parneka}"
        f"&Weight={weight}"
        f"&orderIndex={orderIndex}"
        f"&MachineId={machine_id}"
    )
    try:
        update_wifi_status()
        lcd.move_to(0, 0)
        lcd.putstr(" " * 16)
        lcd.move_to(0, 0)
        lcd.putstr("Sending data...")

        response = requests.post(url, json = {})
        response_json = response.json()
        message = str(response_json.get('message', 'No message'))
        code = response_json.get('code', 0)
        response.close()

        lcd.move_to(0, 0)
        lcd.putstr(" " * 16)
        if code == 200:
            lcd.putstr("Success!")
        elif code == 400:
            lcd.putstr("Bad input!")
        elif code == 404:
            lcd.putstr("Not found!")
        else:
            lcd.putstr("Error!")
        lcd.move_to(1, 0)
        lcd.putstr(message[:16])
        time.sleep(3)
    except Exception as e:
        lcd.move_to(0, 0)
        lcd.putstr(" " * 16)
        lcd.putstr("fail" + str(e)[:16])
        time.sleep(2)

def select_in_out_menu():
    """Handles IN/OUT selection, OTA trigger, returns 'IN' or 'OUT'"""
    in_out_selection = None
    last_key = None
    #
    #  ----------------
    # |Select IN/OUT:  |
    # |1:IN  2:OUT     |
    #  ----------------
    lcd.move_to(0, 0)
    lcd.putstr("                ")
    lcd.move_to(0, 0)
    lcd.putstr("Select IN/OUT:")
    lcd.move_to(1, 0)
    lcd.putstr("1:IN 2:OUT 3:Vac")
    while in_out_selection is None:
        update_wifi_status()
        key = scan_keypad()
        if key and key != last_key:
            if key == '1':
                in_out_selection = 'IN'
            elif key == '2':
                in_out_selection = 'OUT'
            elif key == '3':
                in_out_selection = 'Vacuum'
            elif key == '*':
                trigger_ota_update()
                # After OTA, restart IN/OUT selection prompt
                lcd.move_to(0, 0)
                lcd.putstr("                ")
                lcd.move_to(0, 0)
                lcd.putstr("Select IN/OUT:")
                lcd.move_to(1, 0)
                lcd.putstr("1:IN 2:OUT 3:Vac")
                last_key = key
                continue
            last_key = key
        elif not key:
            last_key = None
        time.sleep_ms(100)
    #
    #  ----------------
    # |Selected: IN    |
    # |                |
    #  ----------------
    # or
    #  ----------------
    # |Selected: OUT   |
    # |                |
    #  ----------------
    lcd.move_to(0, 0)
    lcd.putstr("                ")
    lcd.move_to(0, 0)
    lcd.putstr(f"Selected: {in_out_selection}")
    lcd.move_to(1, 0)
    lcd.putstr("                ")
    time.sleep(1)
    return in_out_selection

def input_barnika_quantity_menu():
    """Handles barnika quantity input, returns quantity as string"""
    barnika_quantity = ""
    last_key = None
    #
    #  ----------------
    # |Barnika Qty:    |
    # |Press # to conf.|
    #  ----------------
    lcd.move_to(0, 0)
    lcd.putstr("                ")
    lcd.move_to(0, 0)
    lcd.putstr("Barnika Qty:")
    lcd.move_to(1, 0)
    lcd.putstr("Press # to confirm")
    while True:
        update_wifi_status()
        key = scan_keypad()
        if key and key != last_key:
            if key == '#':
                if barnika_quantity:
                    break
                else:
                    #
                    #  ----------------
                    # |Enter quantity! |
                    # |                |
                    #  ----------------
                    lcd.move_to(0, 0)
                    lcd.putstr("                ")
                    lcd.move_to(0, 0)
                    lcd.putstr("Enter quantity!")
                    time.sleep(1)
                    #
                    #  ----------------
                    # |Barnika Qty:    |
                    # |Press # to conf.|
                    #  ----------------
                    lcd.move_to(0, 0)
                    lcd.putstr("Barnika Qty:")
                    lcd.move_to(1, 0)
                    lcd.putstr("Press # to confirm")
            elif key == 'D':  # Backspace
                barnika_quantity = barnika_quantity[:-1]
                #
                #  ----------------
                # |Barnika Qty:    |
                # |<current input> |
                #  ----------------
                lcd.move_to(0, 0)
                lcd.putstr("                ")
                lcd.move_to(0, 0)
                lcd.putstr("Barnika Qty:")
                lcd.move_to(1, 0)
                lcd.putstr("                ")
                lcd.move_to(1, 0)
                lcd.putstr(barnika_quantity[:16])
            elif key in '0123456789':
                barnika_quantity += key
                #
                #  ----------------
                # |Barnika Qty:    |
                # |<current input> |
                #  ----------------
                lcd.move_to(0, 0)
                lcd.putstr("                ")
                lcd.move_to(0, 0)
                lcd.putstr("Barnika Qty:")
                lcd.move_to(1, 0)
                lcd.putstr("                ")
                lcd.move_to(1, 0)
                lcd.putstr(barnika_quantity[:16])
            last_key = key
        elif not key:
            last_key = None
        time.sleep_ms(100)
    #
    #  ----------------
    # |Qty: <quantity> |
    # |                |
    #  ----------------
    lcd.move_to(0, 0)
    lcd.putstr("                ")
    lcd.move_to(0, 0)
    lcd.putstr(f"Qty: {barnika_quantity}")
    lcd.move_to(1, 0)
    lcd.putstr("                ")
    time.sleep(1)
    return barnika_quantity

def select_type_menu():
    """Handles type selection, OTA trigger, returns type as int"""
    number_buffer = ""
    selected_type = None
    last_key = None
    #
    #  ----------------
    # |Enter Type:     |
    # |Press # to conf.|
    #  ----------------
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

    # Step 4: Display Selection
    lcd.move_to(0, 0)
    lcd.putstr("                ")
    lcd.move_to(0, 0)
    lcd.putstr("Selected Type:")
    lcd.move_to(0, 14)
    lcd.putstr(str(selected_type))
    time.sleep(1)
    return selected_type

def select_status_menu():
    """Handles piece status selection, returns status as int (1=E, 2=S, 3=G)"""
    piece_status = None
    last_key = None
    
    lcd.move_to(0, 0)
    lcd.putstr("                ")
    lcd.move_to(0, 0)
    lcd.putstr("1:E 2:S 3:G")
    lcd.move_to(1, 0)
    lcd.putstr("                ")
    lcd.move_to(1, 0)
    lcd.putstr("Select status:")
    
    while piece_status is None:
        update_wifi_status()
        key = scan_keypad()
        if key and key != last_key:
            if key in ['1', '2', '3']:
                piece_status = int(key)
                lcd.move_to(0, 0)
                lcd.putstr("                ")
                lcd.move_to(0, 0)
                if piece_status == 1:
                    lcd.putstr("E3dam sel.")
                elif piece_status == 2:
                    lcd.putstr("Esteb3ad sel.")
                elif piece_status == 3:
                    lcd.putstr("Good sel.")
                lcd.move_to(1, 0)
                lcd.putstr("                ")
                time.sleep(1)
            elif key == '*':  # OTA Update trigger
                trigger_ota_update()
                # After OTA, restart status selection
                lcd.move_to(0, 0)
                lcd.putstr("                ")
                lcd.move_to(0, 0)
                lcd.putstr("1:E 2:S 3:G")
                lcd.move_to(1, 0)
                lcd.putstr("Select status:")
                last_key = key
                continue
            last_key = key
        elif not key:
            last_key = None
        time.sleep_ms(100)
    
    return piece_status

def wait_for_weight_menu():
    """Handles waiting for and receiving weight, returns weight as string"""
    lcd.move_to(0, 0)
    lcd.putstr("                ")
    lcd.move_to(0, 0)
    lcd.putstr("Waiting weight..")
    update_wifi_status()

    # Step 6: Receive Weight from Sensor
    received_weight = receive_number()
    # received_weight = "1000"

    # Step 7: Display Weight
    lcd.move_to(0, 0)
    lcd.putstr("                ")
    lcd.move_to(0, 0)
    lcd.putstr("Weight:")
    lcd.move_to(1, 0)
    lcd.putstr("                ")
    lcd.move_to(1, 0)
    lcd.putstr(received_weight[:16])
    update_wifi_status()
    time.sleep(1)
    return received_weight

def input_deducted_weight_menu():
    """Handles deducted weight input, returns deducted weight as string"""
    deducted_weight = ""
    last_key = None
    lcd.move_to(0, 0)
    lcd.putstr("                ")
    lcd.move_to(0, 0)
    lcd.putstr("Deduct Weight:")
    lcd.move_to(1, 0)
    lcd.putstr("Press # to conf.")
    while True:
        update_wifi_status()
        key = scan_keypad()
        if key and key != last_key:
            if key == '#':
                if deducted_weight:
                    break
                else:
                    lcd.move_to(0, 0)
                    lcd.putstr("                ")
                    lcd.move_to(0, 0)
                    lcd.putstr("Enter weight!")
                    time.sleep(1)
                    lcd.move_to(0, 0)
                    lcd.putstr("Deduct Weight:")
                    lcd.move_to(1, 0)
                    lcd.putstr("Press # to conf.")
            elif key == 'D':  # Backspace
                deducted_weight = deducted_weight[:-1]
                lcd.move_to(0, 0)
                lcd.putstr("                ")
                lcd.move_to(0, 0)
                lcd.putstr("Deduct Weight:")
                lcd.move_to(1, 0)
                lcd.putstr(deducted_weight[:16])
            elif key == '*':  # Decimal point
                if '.' not in deducted_weight:
                    deducted_weight += '.'
                lcd.move_to(0, 0)
                lcd.putstr("                ")
                lcd.move_to(0, 0)
                lcd.putstr("Deduct Weight:")
                lcd.move_to(1, 0)
                lcd.putstr("                ")
                lcd.move_to(1, 0)
                lcd.putstr(deducted_weight[:16])
            elif key in '0123456789.':
                deducted_weight += key
                lcd.move_to(0, 0)
                lcd.putstr("                ")
                lcd.move_to(0, 0)
                lcd.putstr("Deduct Weight:")
                lcd.move_to(1, 0)
                lcd.putstr("                ")
                lcd.move_to(1, 0)
                lcd.putstr(deducted_weight[:16])
            last_key = key
        elif not key:
            last_key = None
        time.sleep_ms(100)
    update_wifi_status()
    time.sleep(2)
    return deducted_weight

def show_weight_difference_menu(received_weight, deducted_weight):
    """Shows the difference between received and deducted weight, waits for confirmation"""
    try:
        # Convert to float for calculation
        received = float(received_weight)
        deducted = float(deducted_weight)
        difference = received - deducted
        
        # Format difference to 2 decimal places
        difference_str = f"{difference:.2f}"
        
        lcd.move_to(0, 0)
        lcd.putstr("                ")
        lcd.move_to(0, 0)
        lcd.putstr("Difference:")
        lcd.move_to(1, 0)
        lcd.putstr("                ")
        lcd.move_to(1, 0)
        lcd.putstr(difference_str[:16])
        
        # Wait for user confirmation
        last_key = None
        while True:
            update_wifi_status()
            key = scan_keypad()
            if key and key != last_key:
                if key == '#':  # Confirm
                    lcd.move_to(0, 0)
                    lcd.putstr("                ")
                    lcd.move_to(0, 0)
                    lcd.putstr("Confirmed!")
                    lcd.move_to(1, 0)
                    lcd.putstr("                ")
                    time.sleep(1)
                    return difference_str
                elif key == '*':  # OTA Update trigger
                    trigger_ota_update()
                    # After OTA, restart difference display
                    lcd.move_to(0, 0)
                    lcd.putstr("                ")
                    lcd.move_to(0, 0)
                    lcd.putstr("Difference:")
                    lcd.move_to(1, 0)
                    lcd.putstr("                ")
                    lcd.move_to(1, 0)
                    lcd.putstr(difference_str[:16])
                    last_key = key
                    continue
                last_key = key
            elif not key:
                last_key = None
            time.sleep_ms(100)
            
    except ValueError:
        # Handle invalid number conversion
        lcd.move_to(0, 0)
        lcd.putstr("                ")
        lcd.move_to(0, 0)
        lcd.putstr("Invalid weight!")
        lcd.move_to(1, 0)
        lcd.putstr("                ")
        time.sleep(2)
        return "0.00"

def send_to_api_menu(status, barnika_quantity, type_id, deducted_weight, received_weight, orderIndex):
    """Sends data to API, handles response display"""
    try:
        send_pre_cutting_item(status, barnika_quantity, type_id, deducted_weight, received_weight, orderIndex)
    except Exception as e:
        lcd.move_to(0, 0)
        lcd.putstr("                ")
        lcd.move_to(0, 0)
        lcd.putstr("Error:")
        lcd.move_to(0, 6)
        lcd.putstr(str(e)[:10])

def show_success_menu():
    """Shows success message"""
    lcd.move_to(0, 0)
    lcd.putstr("                ")
    lcd.move_to(0, 0)
    lcd.putstr("Done!")
    lcd.move_to(1, 0)
    lcd.putstr("                ")
    update_wifi_status()
    time.sleep(2)

def select_order_number():
    """Get order number from user input"""
    order_buffer = ""
    last_key = None

    update_wifi_status(force=True)
    lcd.move_to(0, 0)
    lcd.putstr("                ")
    lcd.move_to(0, 0)
    lcd.putstr("Enter Order No:")
    lcd.move_to(1, 0)
    lcd.putstr("Press # to confirm")

    while True:
        update_wifi_status()
        key = scan_keypad()
        if key and key != last_key:
            if key == '#':  # Confirm order number
                if order_buffer:
                    lcd.move_to(0, 0)
                    lcd.putstr("                ")
                    lcd.move_to(0, 0)
                    lcd.putstr("Order Confirmed:")
                    lcd.move_to(1, 0)
                    lcd.putstr("No: " + order_buffer[:12])
                    time.sleep(1)
                    return order_buffer
                else:
                    lcd.move_to(0, 0)
                    lcd.putstr("                ")
                    lcd.move_to(0, 0)
                    lcd.putstr("Enter a number!")
                    time.sleep(1)
                    lcd.move_to(0, 0)
                    lcd.putstr("                ")
                    lcd.move_to(0, 0)
                    lcd.putstr("Enter Order No:")
                    lcd.move_to(1, 0)
                    lcd.putstr("Press # to confirm")
            elif key == 'D':  # Backspace
                order_buffer = order_buffer[:-1]
                lcd.move_to(0, 0)
                lcd.putstr("                ")
                lcd.move_to(0, 0)
                lcd.putstr("Order No:")
                lcd.move_to(1, 0)
                lcd.putstr("                ")
                lcd.move_to(1, 0)
                lcd.putstr(order_buffer[:16])
                lcd.move_to(0, 0)
                lcd.putstr("Order No:")
                lcd.move_to(1, 0)
                lcd.putstr("Press # to confirm")
            elif key == '*':  # OTA Update trigger
                trigger_ota_update()
                # After OTA, restart order number input
                lcd.move_to(0, 0)
                lcd.putstr("                ")
                lcd.move_to(0, 0)
                lcd.putstr("Enter Order No:")
                lcd.move_to(1, 0)
                lcd.putstr("Press # to confirm")
                last_key = key
                continue
            elif key in '0123456789':  # Number input
                order_buffer += key
                lcd.move_to(0, 0)
                lcd.putstr("                ")
                lcd.move_to(0, 0)
                lcd.putstr("Order No:")
                lcd.move_to(0, 9)
                lcd.putstr(order_buffer)
                lcd.move_to(1, 0)
                lcd.putstr("Press # to confirm")
            last_key = key
        elif not key:
            last_key = None
        time.sleep_ms(100)

def main():
    """Main application loop"""
    connect_wifi()

    orderIndex = select_order_number()

    while True:
        type_id = select_type_menu()
        deducted_weight = input_deducted_weight_menu()
        received_weight = wait_for_weight_menu()
        # Show weight difference and get confirmation
        final_weight = show_weight_difference_menu(received_weight, deducted_weight)
        status = select_in_out_menu()
        # status = select_status_menu()
        # barnika_quantity = input_barnika_quantity_menu()
        if status == 'Vacuum':
            send_to_api_menu('IN', "1", type_id, deducted_weight, received_weight, orderIndex)
            send_to_api_menu('OUT', "1", type_id, deducted_weight, received_weight, orderIndex)
        else:
            send_to_api_menu(status, "1", type_id, deducted_weight, received_weight, orderIndex)
        show_success_menu()

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