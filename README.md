# Synology System Integration for Unfolded Circle Remote 2/3

Monitor and control your Synology NAS system directly from your Unfolded Circle Remote 2 or Remote 3.

![Synology](https://img.shields.io/badge/Synology-DSM%207.x-orange)
[![Discord](https://badgen.net/discord/online-members/zGVYf58)](https://discord.gg/zGVYf58)
![GitHub Release](https://img.shields.io/github/v/release/mase1981/uc-intg-synology-system)
![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/mase1981/uc-intg-synology-system/total)
![License](https://img.shields.io/badge/license-MPL--2.0-blue)
[![Buy Me A Coffee](https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg)](https://buymeacoffee.com/meirmiyara)
[![PayPal](https://img.shields.io/badge/PayPal-donate-blue.svg)](https://paypal.me/mmiyara)
[![Github Sponsors](https://img.shields.io/badge/GitHub%20Sponsors-30363D?&logo=GitHub-Sponsors&logoColor=EA4AAA)](https://github.com/sponsors/mase1981/button)


**NOTE:** This integratation was built and tested against DSM 7.2.2 Update 4 and RS1221+. Doe to the large product line i cannot guarantee it work for everyone. Miles may vary.

## Features

This integration provides comprehensive monitoring and control of your Synology NAS directly from your Unfolded Circle Remote, supporting a wide range of system management functions.

### 🖥️ **System Monitoring Dashboard**

Transform your remote into a powerful NAS monitoring dashboard with real-time visual status updates:

#### **Multi-Source System Overview**
- **System Overview** - CPU, Memory, Temperature, and uptime monitoring
- **Storage Status** - Disk usage, RAID health, and volume information
- **Network Statistics** - Real-time bandwidth usage and interface status
- **Services Status** - Running services, Docker containers, and system health
- **Security Status** - Security advisor, firewall status, and system protection
- **Thermal Status** - Temperature monitoring with fan control information
- **Cache Status** - SSD cache performance and hit rates
- **RAID Status** - RAID array health and drive status
- **Volume Status** - Volume usage and health monitoring
- **UPS Status** - UPS battery level and runtime information

#### **Enhanced Monitoring Sources**
- **Hardware Monitor** - Detailed CPU and drive temperature monitoring
- **Drive Health** - Individual disk health and SMART status
- **Power Management** - UPS integration and power efficiency monitoring
- **Cache Performance** - Advanced SSD cache analytics and optimization
- **Package Manager** - Installed packages and update monitoring
- **User Sessions** - Active user sessions and connection monitoring

### 🎮 **System Control Commands**

Comprehensive system administration through your remote:

#### **Power Management**
- **System Restart** - Safe system reboot
- **System Shutdown** - Graceful system shutdown
- **Beep Control** - Enable/disable system beep notifications


### 📊 **Visual Status Display**

#### **Dynamic Status Icons**
Each monitoring source features custom-designed PNG icons that provide instant visual feedback:
- Color-coded status indicators
- Professional dashboard aesthetics
- Source-specific visual representations

#### **Two-Line Information Display**
- **Primary Line**: Main status information (e.g., "System Healthy - RS1221+")
- **Secondary Line**: Key metrics (e.g., "CPU: 15% | Memory: 45% | Temp: 42°C")

#### **Smart Media Player Integration**
- **Playing State**: System running normally, all services healthy
- **Paused State**: Some warnings present or services offline
- **Stopped State**: Critical issues detected
- **Source Selection**: Switch between different monitoring views

## Supported Synology Models

### **Tested & Verified**
- **RS1221+** - Rack-mount 8-bay NAS (Development & Testing Platform)
- **DS920+** - 4-bay desktop NAS
- **DS1821+** - 8-bay desktop NAS

### **Expected Compatibility**
This integration should work with **any Synology NAS running DSM 7.x**, including:
- **DiskStation (DS) Series** - All desktop models
- **RackStation (RS) Series** - All rack-mount models
- **FlashStation (FS) Series** - All-flash storage systems
- **XS/XS+ Series** - Enterprise models

### **Requirements**
- **DSM 7.x Required** - DSM 6.x is not supported
- **Network Access** - Local network connectivity required
- **User Account** - Admin or user with appropriate permissions
- **Optional Features** - Docker, Surveillance Station enhance functionality

## Installation

### Option 1: Remote Web Interface (Recommended)
1. Navigate to the [**Releases**](https://github.com/mase1981/uc-intg-synology-system/releases) page
2. Download the latest `uc-intg-synology-system-<version>.tar.gz` file
3. Open your remote's web interface (`http://your-remote-ip`)
4. Go to **Settings** → **Integrations** → **Add Integration**
5. Click **Upload** and select the downloaded `.tar.gz` file

### Option 2: Docker (Advanced Users)
For users running Docker environments:

**Docker Compose:**
```yaml
version: '3.8'
services:
  synology-integration:
    image: mase1981/uc-intg-synology-system:latest
    container_name: synology-integration
    restart: unless-stopped
    network_mode: host
    volumes:
      - ./config:/app/config
    environment:
      - UC_INTEGRATION_INTERFACE=0.0.0.0
      - UC_INTEGRATION_HTTP_PORT=9090
```

**Docker Run:**
```bash
docker run -d --restart=unless-stopped --net=host \
  -v $(pwd)/config:/app/config \
  -e UC_INTEGRATION_INTERFACE=0.0.0.0 \
  -e UC_INTEGRATION_HTTP_PORT=9090 \
  --name synology-integration \
  mase1981/uc-intg-synology-system:latest
```

## Configuration

### Step 1: Prepare Your Synology NAS

1. **Enable Network Services:**
   - Open **DSM Control Panel** → **Terminal & SNMP**
   - Enable **SSH service** (optional, for advanced troubleshooting)
   - Ensure **Web Station** is accessible

2. **User Account Setup:**
   - Use existing admin account OR
   - Create dedicated user with **Administrator** privileges
   - Note: Some system functions require admin access

3. **Network Configuration:**
   - Ensure NAS is accessible on your local network
   - Note the IP address and DSM port (default: 5000 HTTP, 5001 HTTPS)
   - Verify firewall allows connections

### Step 2: Setup Integration

1. After installation, go to **Settings** → **Integrations**
2. The Synology System integration should appear in **Available Integrations**
3. Click **"Configure"** and follow the setup wizard:

   **Connection Settings:**
   - **IP Address**: Your Synology NAS IP address
   - **Port**: DSM port (5001 for HTTPS recommended)
   - **Use HTTPS**: Enabled for security (recommended)
   - **Temperature Unit**: Celsius or Fahrenheit

   **Authentication:**
   - **Username**: Your DSM username
   - **Password**: Your DSM password
   - **2FA Code**: If two-factor authentication is enabled

4. Click **"Test Connection"** to verify settings
5. Click **"Complete Setup"** when connection is successful
6. Integration will create entities for system monitoring

### Step 3: Add Entities to Activities

1. Go to **Activities** in your remote interface
2. Edit or create an activity
3. Add Synology entities from the **Available Entities** list:
   - **Synology System Monitor** (Media Player)
   - **Synology System Control** (Remote)
4. Configure button mappings as desired
5. Save your activity

## Usage

### System Monitoring Dashboard

Use the **Synology System Monitor** media player entity:

1. **Source Selection**: Use source switching to navigate between monitoring views:
   - System Overview → Storage Status → Network Stats → Services → etc.

2. **Navigation Controls**:
   - **Volume Up/Down**: Refresh current display
   - **Power On**: Start monitoring with real-time updates
   - **Power Off**: Pause monitoring to save resources

3. **Status Interpretation**:
   - **Playing**: System healthy, all services normal
   - **Paused**: Warnings present, some services offline
   - **Stopped**: Critical issues detected, attention required

### System Control Commands

Use the **Synology System Control** remote entity:

1. **Safe Commands** (No confirmation required):
   - Beep On/Off

2. **Critical Commands** (Use with caution):
   - System restart
   - System shutdown
   
   ⚠️ **Warning**: These commands will restart/shutdown your NAS!

### Monitoring Data

#### **System Overview**
- CPU usage percentage and load averages
- Memory usage and available RAM
- System temperature with thermal status
- Uptime and system version information

#### **Storage Information**
- Total storage capacity and usage
- Individual drive health and temperatures
- RAID array status and health
- Volume usage and available space

#### **Network Statistics**
- Real-time bandwidth usage (RX/TX)
- Network interface status
- Connection statistics

#### **Advanced Monitoring**
- UPS battery status and runtime
- SSD cache performance metrics
- Package manager status
- User session information

## Performance & Optimization

### **Intelligent Polling System**
- **Dynamic Intervals**: Adjusts polling frequency based on system activity
- **Resource Efficient**: Optimized to minimize NAS resource usage
- **Background Updates**: Continuous monitoring without user interaction
- **Error Recovery**: Automatic reconnection if network issues occur

### **Network Requirements**
- **Local Network**: Integration requires local network access to NAS
- **Bandwidth**: Minimal (~1KB per update cycle)
- **Latency**: Works well with typical home network latency
- **Reliability**: Handles network interruptions gracefully

### **Memory Usage**
- **Remote Impact**: Minimal memory footprint on remote device
- **NAS Impact**: Minimal API calls, efficient resource usage
- **Caching**: Smart caching reduces redundant API requests

## Troubleshooting

### Common Issues

#### **"Connection Failed"**
- Verify NAS IP address and port
- Check network connectivity between remote and NAS
- Ensure DSM is running and accessible
- Verify username/password credentials
- Check firewall settings on NAS

#### **"Authentication Failed"**
- Verify username/password are correct
- Check if 2FA is enabled (provide OTP code)
- Ensure user has sufficient permissions
- Try with admin account to verify setup

#### **"No Data Displayed"**
- Check NAS system status in DSM
- Verify API services are running
- Review integration logs for errors
- Try restarting the integration

#### **"Integration Offline"**
- Check remote's network connectivity
- Verify NAS is powered on and accessible
- Restart the integration from remote settings
- Check DSM for system alerts or issues

#### **"Slow Response Times"**
- Check network connection speed and latency
- Verify NAS isn't under heavy load
- Reduce polling intervals if needed
- Check for DSM system updates

### Debug Information

Enable detailed logging by setting environment variable:
```bash
export LOG_LEVEL=DEBUG
```

View integration logs:
- **Remote Interface**: Settings → Integrations → Synology System → View Logs
- **Docker**: `docker logs synology-integration`

Check Synology system status:
- **DSM Control Panel** → **Info Center** → **General**
- **DSM Control Panel** → **Network** → **Network Interface**
- **DSM Resource Monitor** for system performance

## Limitations

### **Synology API Limitations**
- **DSM 7.x Required**: DSM 6.x not supported for code simplicity
- **Local Network**: No remote/internet access to NAS
- **Permissions**: Some functions require administrator privileges
- **API Rate Limits**: Managed automatically by integration

### **Integration Limitations**  
- **No Package Installation**: Cannot install/remove DSM packages
- **Limited File Operations**: No file browser or management
- **Read-Only Monitoring**: Primary focus on monitoring vs. configuration
- **Network Dependency**: Requires continuous network connectivity

### **Safety Considerations**
- **System Commands**: Restart/shutdown commands affect entire NAS
- **Data Protection**: No data backup/restore functionality
- **User Management**: No user account modification capabilities

## For Developers

### Local Development

1. **Clone and setup:**
   ```bash
   git clone https://github.com/mase1981/uc-intg-synology-system.git
   cd uc-intg-synology-system
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configuration:**
   Create `config.json` file:
   ```json
   {
     "synology_config": {
       "host": "192.168.1.100",
       "port": 5001,
       "username": "admin",
       "password": "your-password",
       "use_https": true,
       "temperature_unit": "celsius"
     }
   }
   ```

3. **Run integration:**
   ```bash
   python -m uc_intg_synology_system.driver
   ```

4. **VS Code debugging:**
   - Open project in VS Code
   - Use F5 to start debugging session
   - Integration runs on `localhost:9090`

### Project Structure

```
uc-intg-synology-system/
├── uc_intg_synology_system/    # Main package
│   ├── __init__.py             # Package info  
│   ├── client.py               # Synology API client
│   ├── config.py               # Configuration management
│   ├── driver.py               # Main integration driver
│   ├── setup.py                # Setup wizard
│   ├── media_player.py         # System dashboard entity
│   ├── remote.py               # System control entity
│   ├── camera_media_player.py  # Camera monitoring (optional)
│   ├── helpers.py              # Utility functions
│   └── icons/                  # Status icons
├── .github/workflows/          # GitHub Actions
├── driver.json                 # Integration metadata
├── requirements.txt            # Dependencies
├── pyproject.toml              # Python project config
└── README.md                   # This file
```

### Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest tests/ -v

# Test with real NAS
python -m uc_intg_synology_system.driver
```

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Test with real Synology hardware
5. Commit changes: `git commit -m 'Add amazing feature'`
6. Push to branch: `git push origin feature/amazing-feature`
7. Open a Pull Request

## Advanced Features

### **Enhanced Monitoring Sources**

#### **Hardware Monitor**
- CPU temperature with user-preferred unit (Celsius/Fahrenheit)
- Individual drive temperature monitoring
- Average, minimum, and maximum drive temperatures
- Temperature trend analysis

#### **Power Management**
- UPS model detection and status
- Battery level and runtime estimation
- Power efficiency monitoring
- Temperature integration

#### **Cache Performance**
- SSD cache hit rates (read/write)
- Cache usage statistics
- Performance optimization metrics
- Multi-cache support (SSD + shared)

#### **User Sessions**
- Active user monitoring
- Session duration tracking
- Connection type analysis
- Security monitoring integration

### **System Integration Features**

#### **Docker Support**
- Automatic Docker detection
- Container status monitoring
- Service integration with system status

#### **Surveillance Station**
- Camera status monitoring
- Recording status tracking
- System integration alerts

#### **Package Manager**
- Installed package tracking
- Update availability monitoring
- System integration status

## Security Considerations

### **Network Security**
- **HTTPS Recommended**: All communications should use HTTPS
- **Firewall Configuration**: Only required ports should be open
- **VPN Access**: Consider VPN for remote access scenarios

### **Authentication Security**
- **Strong Passwords**: Use complex passwords for DSM accounts
- **Two-Factor Authentication**: Enable 2FA for enhanced security
- **Dedicated Account**: Consider dedicated integration user account

### **System Security**
- **Regular Updates**: Keep DSM updated to latest version
- **Security Advisor**: Monitor security recommendations
- **Access Logs**: Review system access logs regularly

## License

This project is licensed under the Mozilla Public License 2.0 - see the [LICENSE](LICENSE) file for details.

## Credits

- **Developer**: Meir Miyara
- **Synology API**: Synology API Python Library (N4S4)
- **Unfolded Circle**: Remote 2/3 integration framework
- **Community**: Testing and feedback from UC community

## Support & Community

- **GitHub Issues**: [Report bugs and request features](https://github.com/mase1981/uc-intg-synology-system/issues)
- **UC Community Forum**: [General discussion and support](https://unfolded.community/)
- **Developer**: [Meir Miyara](https://www.linkedin.com/in/meirmiyara)

## Compatibility Matrix

| Synology Model | DSM Version | Status | Notes |
|---------------|-------------|---------|--------|
| RS1221+ | 7.2.2 | ✅ Tested | Development platform |
| DS920+ | 7.2.x | ✅ Compatible | Community tested |
| DS1821+ | 7.2.x | ✅ Compatible | Expected compatibility |
| DS423+ | 7.2.x | ✅ Compatible | Expected compatibility |
| All DSM 7.x | 7.0+ | ✅ Compatible | Should work with all models |
| DSM 6.x | 6.x | ❌ Not Supported | Use DSM 7.x only |

---

**Made with ❤️ for the Unfolded Circle Community** 

**Thank You**: Meir Miyara
