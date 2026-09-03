# Karwa Qatar Mobile Automation Framework

This project contains a Python-based mobile automation system designed to run on **Windows** using **Wireless ADB (Android Debug Bridge)**. It automates the "Karwa Qatar" application to perform wallet top-ups and validates whether target mobile numbers receive OTP codes (generating a valid lead).

## 📂 File & Folder Structure

Here is how the project files are organized in this folder:

```
FARWAN QATAR/
│
├── config.json          # Configuration settings (Device IP/Port, package details, payment method)
├── requirements.txt     # Python libraries needed (opencv-python, numpy, pillow, colorama)
├── leads.csv            # Input spreadsheet containing phone numbers and emails to validate
├── leads_results.csv    # Output spreadsheet where the script writes validation results (OTP_SENT / FAILED)
│
├── adb_manager.py       # Core module for device detection, wireless connection, UI inspection, clicks, & typing
├── automation.py        # Core automation runner containing the Karwa app flow logic and loop
│
├── setup.bat            # One-click installer to set up the Python environment and libraries
├── run.bat              # One-click runner to start the automation process
│
└── debug_logs/          # Folder created automatically to save screenshots & XML layouts for failed steps
```

---

## 🚀 Features

- **No Server Overhead**: Uses direct ADB commands and Android's native `uiautomator` XML dumps. No heavy Appium server setup required!
- **Automatic ADB Setup**: If ADB is not found in your system PATH, the script automatically downloads the Android SDK Platform-Tools for you.
- **Robust WebView Handling**: Leverages dynamic layout inspection. If the webviews (QPAY, Debit screen) are secure and do not expose layout details, the script falls back to **normalized coordinates (screen ratio taps)**.
- **CSV Processing & Progress Resuming**: Processes lists of leads from `leads.csv` and outputs results to `leads_results.csv`. You can pause or stop the script, and it will resume from where it left off.
- **Debug Logs & Screen Captures**: Every transaction captures a screenshot and XML dump in the `debug_logs/` directory for debugging.

---

## 📱 Device Setup (Wireless ADB)

To connect your phone to your PC via Wi-Fi:

1. **Same Wi-Fi Network**: Ensure both your PC and your Android phone are connected to the exact same Wi-Fi network.
2. **Enable Developer Options**:
   - Open Settings on your phone.
   - Go to **About Phone** (or **Software Information**).
   - Tap **Build Number** 7 times until you see the message "You are now a developer!".
3. **Enable Wireless Debugging**:
   - Go back to Settings -> **System** (or **Additional Settings**) -> **Developer Options**.
   - Enable **USB Debugging**.
   - Enable **Wireless Debugging**. 
   - Tap on **Wireless Debugging** to open its details. You will see an **IP address and Port** (e.g. `192.168.1.100:5555` or `192.168.1.100:39845`).
   - Write down this IP address and Port.

---

## ⚙️ Configuration (`config.json`)

Before running the script, open `config.json` and configure it:

```json
{
  "adb_target_ip": "192.168.1.100:5555",
  "app_package": "com.karwatechnologies.karwa",
  "app_activity": "com.karwatechnologies.karwa.MainActivity",
  "payment_method": "Fawran",
  "csv_input_file": "leads.csv",
  "csv_output_file": "leads_results.csv",
  "delay_between_steps": 1.5,
  "element_timeout": 10,
  "restart_app_on_fail": true
}
```

- `adb_target_ip`: Put your phone's wireless debug IP and Port here. **(If you connect via USB cable, leave this blank `""` and the script will target your phone automatically!)**
- `payment_method`: You can specify `"Fawran"`, `"NAPS"`, or `"HIMYAN"` depending on which button you want to click on the QPAY screen.

---

## 📂 CSV Files Structure

### Input: `leads.csv`
Contains the list of numbers you want to validate. Put the file in the project folder.
```csv
phone_number,email,status
+97455001122,customer1@gmail.com,pending
+97433284425,,pending
```
*Note: If the `email` field is empty, the script will automatically generate a random, valid-looking email for that transaction.*

### Output: `leads_results.csv`
Created automatically by the script. It logs the result of each lead:
```csv
phone_number,email,status,timestamp
+97455001122,customer1@gmail.com,OTP_SENT,2026-08-30 14:22:10
+97433284425,random571@gmail.com,FAILED,2026-08-30 14:23:45
```
- `OTP_SENT`: The number is registered/valid, and the OTP verification screen was successfully reached. (Lead is OK).
- `FAILED`: An error message appeared on the screen, or the payment gateway failed to trigger OTP. (Lead is Bad).
- `UNKNOWN`: The screen could not be verified automatically. Check the corresponding screenshot in `debug_logs/` folder to see what happened.

---

## 🏃 How to Run

1. **Step 1**: Double-click **`setup.bat`**. This will set up Python, build the virtual environment, and install dependencies.
2. **Step 2**: Ensure Wireless Debugging is active on your phone and its IP:Port is saved in `config.json`.
3. **Step 3**: Double-click **`run.bat`**. The command line will open and start executing the automation.
