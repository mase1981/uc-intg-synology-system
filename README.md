# Synology System Integration for Unfolded Circle Remote 2/3

Monitor and control your Synology NAS system directly from your Unfolded Circle Remote 2 or Remote 3 with **comprehensive system monitoring**, **real-time status updates**, and **visual dashboard displays**.

![Synology](https://img.shields.io/badge/Synology-DSM%207.x-orange)
[![GitHub Release](https://img.shields.io/github/v/release/mase1981/uc-intg-synology-system?style=flat-square)](https://github.com/mase1981/uc-intg-synology-system/releases)
![License](https://img.shields.io/badge/license-MPL--2.0-blue?style=flat-square)
[![GitHub issues](https://img.shields.io/github/issues/mase1981/uc-intg-synology-system?style=flat-square)](https://github.com/mase1981/uc-intg-synology-system/issues)
[![Community Forum](https://img.shields.io/badge/community-forum-blue?style=flat-square)](https://community.unfoldedcircle.com/)
[![Discord](https://badgen.net/discord/online-members/zGVYf58)](https://discord.gg/zGVYf58)
![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/mase1981/uc-intg-synology-system/total?style=flat-square)
[![Buy Me A Coffee](https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=flat-square)](https://buymeacoffee.com/meirmiyara)
[![PayPal](https://img.shields.io/badge/PayPal-donate-blue.svg?style=flat-square)](https://paypal.me/mmiyara)
[![Github Sponsors](https://img.shields.io/badge/GitHub%20Sponsors-30363D?&logo=GitHub-Sponsors&logoColor=EA4AAA&style=flat-square)](https://github.com/sponsors/mase1981)


## Features

This integration provides comprehensive monitoring and control of Synology NAS systems through the Synology API, delivering seamless integration with your Unfolded Circle Remote for complete system management.

**NOTE:** This integration was built and tested against DSM 7.2.2 Update 4 and RS1221+. Due to the large product line, I cannot guarantee it works for everyone. Mileage may vary.

---
## ❤️ Support Development ❤️

If you find this integration useful, consider supporting development:

[![GitHub Sponsors](https://img.shields.io/badge/Sponsor-GitHub-pink?style=for-the-badge&logo=github)](https://github.com/sponsors/mase1981)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/meirmiyara)
[![PayPal](https://img.shields.io/badge/PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white)](https://paypal.me/mmiyara)

Your support helps maintain this integration. Thank you! ❤️
---

### 🖥️ **System Monitoring Dashboard**

Transform your remote into a powerful NAS monitoring dashboard with real-time visual status updates:

#### **Multi-Source System Overview**
- **System Overview** - CPU, Memory, Temperature, and uptime
- **Storage Status** - Disk usage, RAID health, and volumes
- **Network Statistics** - Real-time bandwidth and interface status
- **Services Status** - Running services and Docker containers
- **Security Status** - Security advisor and firewall status
- **Thermal Status** - Temperature monitoring with fan control
- **Cache Status** - SSD cache performance and hit rates
- **RAID Status** - RAID array health and drive status
- **Volume Status** - Volume usage and health monitoring
- **UPS Status** - UPS battery level and runtime

#### **Enhanced Monitoring Sources**
- **Hardware Monitor** - Detailed CPU and drive temperatures
- **Drive Health** - Individual disk health and SMART status
- **Power Management** - UPS integration and power efficiency
- **Cache Performance** - Advanced SSD cache analytics
- **Package Manager** - Installed packages and updates
- **User Sessions** - Active user sessions and connections

### 🎮 **System Control Commands**

Comprehensive system administration through your remote:

#### **Power Management**
- **System Restart** - Safe system reboot
- **System Shutdown** - Graceful system shutdown
- **Beep Control** - Enable/disable system beep notifications

### 📊 **Visual Status Display**

#### **Dynamic Status Icons**
- **Color-coded Indicators** - Instant visual feedback
- **Professional Dashboard** - Custom-designed PNG icons
- **Source-specific Icons** - Visual representations per source

#### **Two-Line Information Display**
- **Primary Line**: Main status (e.g., "System Healthy - RS1221+")
- **Secondary Line**: Key metrics (e.g., "CPU: 15% | Memory: 45% | Temp: 42°C")

#### **Smart Media Player Integration**
- **Playing State**: System running normally
- **Paused State**: Warnings present or services offline
- **Stopped State**: Critical issues detected
- **Source Selection**: Switch between monitoring views

### **Supported Synology Models**

#### **Tested & Verified**
- **RS1221+** - Rack-mount 8-bay NAS (Development platform)
- **DS920+** - 4-bay desktop NAS
- **DS1821+** - 8-bay desktop NAS

#### **Expected Compatibility**
This integration should work with **any Synology NAS running DSM 7.x**, including:
- **DiskStation (DS) Series** - All desktop models
- **RackStation (RS) Series** - All rack-mount models
- **FlashStation (FS) Series** - All-flash storage
- **XS/XS+ Series** - Enterprise models

### **API Requirements**

- **Protocol**: Synology DSM API
- **DSM Version**: 7.x required (DSM 6.x not supported)
- **User Account**: Admin or user with appropriate permissions
- **Port**: Default 5000 (HTTP) or 5001 (HTTPS)
- **Connection**: Local network access required

### **Network Requirements**

- **Local Network Access** - Integration requires same network as NAS
- **HTTPS Protocol** - Recommended for security
- **Static IP Recommended** - Device should have static IP or DHCP reservation
- **Firewall** - Must allow HTTP/HTTPS traffic
- **Network Isolation** - Must be on same subnet as Remote

## Installation

### Option 1: Remote Web Interface (Recommended)
1. Navigate to the [**Releases**](https://github.com/mase1981/uc-intg-synology-system/releases) page
2. Download the latest `uc-intg-synology-system-<version>-aarch64.tar.gz` file
3. Open your remote's web interface (`http://your-remote-ip`)
4. Go to **Settings** → **Integrations** → **Add Integration**
5. Click **Upload** and select the downloaded `.tar.gz` file

### Option 2: Docker (Advanced Users)

The integration is available as a pre-built Docker image from Docker Hub:

**Image**: `mase1981/uc-intg-synology-system:latest`

**Docker Compose:**
```yaml
services:
  uc-intg-synology-system:
    image: mase1981/uc-intg-synology-system:latest
    container_name: uc-intg-synology-system
    network_mode: host
    volumes:
      - </local/path>:/config
    environment:
      - UC_CONFIG_HOME=/config
      - UC_INTEGRATION_HTTP_PORT=9090
      - UC_INTEGRATION_INTERFACE=0.0.0.0
      - PYTHONPATH=/app
    restart: unless-stopped
```

**Docker Run:**
```bash
docker run -d --name uc-intg-synology-system --restart unless-stopped --network host -v synology-config:/config -e UC_CONFIG_HOME=/config -e UC_INTEGRATION_INTERFACE=0.0.0.0 -e UC_INTEGRATION_HTTP_PORT=9090 -e PYTHONPATH=/app mase1981/uc-intg-synology-system:latest
```

## Configuration

### Step 1: Prepare Your Synology NAS

**IMPORTANT**: Synology NAS must be powered on and connected to your network before adding the integration.

#### Enable Network Services:
1. Open **DSM Control Panel** → **Terminal & SNMP**
2. Enable **SSH service** (optional, for advanced troubleshooting)
3. Ensure **Web Station** is accessible

#### User Account Setup:
- Use existing admin account OR
- Create dedicated user with **Administrator** privileges
- Note: Some system functions require admin access

#### Network Configuration:
- Ensure NAS is accessible on your local network
- Note the IP address and DSM port (default: 5000 HTTP, 5001 HTTPS)
- Verify firewall allows connections

### Step 2: Setup Integration

1. After installation, go to **Settings** → **Integrations**
2. The Synology System integration should appear in **Available Integrations**
3. Click **"Configure"** to begin setup:

#### **Connection Settings:**
- **IP Address**: Your Synology NAS IP address
- **Port**: DSM port (5001 for HTTPS recommended)
- **Use HTTPS**: Enabled for security (recommended)
- **Temperature Unit**: Celsius or Fahrenheit

#### **Authentication:**
- **Username**: Your DSM username
- **Password**: Your DSM password
- **2FA Code**: If two-factor authentication is enabled

#### **Connection Test:**
- Integration will test your Synology API credentials
- Verify your Synology profile is accessible
- Setup fails if device unreachable

4. Integration will create entities:
   - **Synology System Monitor**: Media Player entity for dashboard
   - **Synology System Control**: Remote entity for system commands

## Using the Integration

### System Monitoring Dashboard

The media player entity provides comprehensive monitoring:

- **Source Selection**: Navigate between monitoring views
  - System Overview → Storage Status → Network Stats → Services
- **Navigation Controls**:
  - **Volume Up/Down**: Refresh current display
  - **Power On**: Start monitoring with real-time updates
  - **Power Off**: Pause monitoring to save resources
- **Status Interpretation**:
  - **Playing**: System healthy, all services normal
  - **Paused**: Warnings present, some services offline
  - **Stopped**: Critical issues detected

### System Control Commands

The remote entity provides system administration:

- **Safe Commands**: Beep On/Off (no confirmation required)
- **Critical Commands**: System restart, shutdown (use with caution)

### Monitoring Data

| Category | Information Displayed |
|----------|----------------------|
| System Overview | CPU usage, memory, temperature, uptime |
| Storage | Capacity, usage, drive health, RAID status |
| Network | Bandwidth (RX/TX), interface status |
| Advanced | UPS status, SSD cache, packages, user sessions |

## Credits

- **Developer**: Meir Miyara
- **Synology API**: Synology API Python Library (N4S4)
- **Unfolded Circle**: Remote 2/3 integration framework (ucapi)
- **Protocol**: Synology DSM API
- **Community**: Testing and feedback from UC community

## License

This project is licensed under the Mozilla Public License 2.0 (MPL-2.0) - see LICENSE file for details.

## Support & Community

- **GitHub Issues**: [Report bugs and request features](https://github.com/mase1981/uc-intg-synology-system/issues)
- **UC Community Forum**: [General discussion and support](https://unfolded.community/)
- **Developer**: [Meir Miyara](https://www.linkedin.com/in/meirmiyara)
- **Synology Support**: [Official Synology Support](https://www.synology.com/support)

---

**Made with ❤️ for the Unfolded Circle and Synology Communities**

**Thank You**: Meir Miyara
