# Auto-Snap MCP 📸

**Automated screenshot capture and document processing for MCP Clients**

Turn your screenshots into PDFs automatically! Auto-Snap lets your MCP client capture windows, process documents, and create PDFs with simple natural language commands.

## 🚀 Quick Start

### Which Option Should I Choose?

- **🐳 Docker** → Zero setup, works everywhere (recommended)
- **🪟 WSL2** → Windows users with WSL2 installed
- **🐧 Linux** → Native Linux

### Setup Steps

**1. Get Auto-Snap:**
```bash
git clone https://github.com/your-repo/auto-snap-mcp
cd auto-snap-mcp
```

**2. Install dependencies (Linux only):**
```bash
# Skip this step if using Docker
sudo apt install -y wmctrl xdotool tesseract-ocr
uv sync
```

**3. Configure Claude Desktop:**

Edit `~/.claude/claude_desktop_config.json` and add **one** of these:

**🐳 Docker (Recommended - No setup needed!)**
```json
{
  "mcpServers": {
    "auto-snap-mcp": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "DISPLAY=:0", 
        "-v", "/tmp/.X11-unix:/tmp/.X11-unix:rw",
        "-v", "${HOME}/auto-snap-captures:/app/captures:rw",
        "mcp/auto-snap-mcp:latest"
      ]
    }
  }
}
```

**🪟 WSL2 (Windows with WSL2)**
```json
{
  "mcpServers": {
    "auto-snap-mcp": {
      "command": "wsl.exe",
      "args": [
        "bash", "-c",
        "cd /home/YOUR_WSL_USERNAME/auto-snap-mcp && DISPLAY=:0 /home/YOUR_WSL_USERNAME/.local/bin/uv run python server.py"
      ]
    }
  }
}
```

**🐧 Linux Native**
```json
{
  "mcpServers": {
    "auto-snap-mcp": {
      "command": "uv",
      "args": ["run", "python", "server.py"],
      "cwd": "/home/YOUR_USERNAME/auto-snap-mcp",
      "env": {"DISPLAY": ":0"}
    }
  }
}
```

**4. Restart Claude Desktop** and verify it works:
- *"List all my open windows"* ← Start with this to test the connection
- *"Capture this PDF and convert to images"*
- *"Take 5 screenshots and make them into a PDF"*

**✅ Working?** You should see your windows listed. If not, check the [🚨 Not Working?](#-not-working) section below.

## 📁 Where Your Files Are Saved

**By default, all your captures go to:**
```
~/auto-snap-captures/
```

**Full path examples:**
- Linux: `/home/username/auto-snap-captures/`
- WSL2: `/home/username/auto-snap-captures/`
- Windows (Docker): `C:\Users\username\auto-snap-captures\`

## ✨ What It Does & Commands to Try

### 📋 **Document Capture**
- Screenshot any window or the entire screen
- Capture multi-page documents automatically
- Works with PDFs, presentations, web pages

### 🔍 **Image Processing**
- Extract text from screenshots (OCR)
- Enhance image quality automatically
- Process multiple images at once

### 📄 **PDF Creation**
- Convert screenshots to PDF instantly
- Organize files with smart naming
- Compress PDFs for smaller size

### 🎯 **Commands to Try**

**"Capture this document as PDF"** → Takes screenshots and creates a PDF

**"Extract text from these images"** → Runs OCR on screenshots  

**"Archive this presentation"** → Screenshots all slides into one PDF

**"List all my open windows"** → See what you can capture

**"Take 5 screenshots and make them into a PDF"** → Multi-page capture

**💡 Pro Tips:**
- **Be specific**: *"Capture the Chrome window"* works better than *"take a screenshot"*
- **Multi-step**: *"Screenshot this presentation and extract all the text"*
- **Batch work**: *"Process all images in my Downloads and make PDFs"*

Want to change where files are saved? See the [🎨 Customize Your Captures](#-customize-your-captures) section below.

## 🛠️ System Support

- ✅ **Linux** (native X11)
- ✅ **WSL2** (Windows apps from Linux)  
- ⚠️ **macOS** (with XQuartz - experimental)

## 🚨 Not Working?

**Common fixes:**

```bash
# Check dependencies
uv run python -c "from capture import check_dependencies; print(check_dependencies())"

# Fix X11 display
export DISPLAY=:0

# Test the server
uv run python server.py
```

**Still stuck?**
1. Make sure the config path is correct: `~/.claude/claude_desktop_config.json`
2. Restart Claude Desktop after config changes
3. Check Claude Desktop logs for errors

## 🎨 Customize Your Captures

**Set where files go:**
```bash
export AUTO_SNAP_OUTPUT_DIR="$HOME/Documents/Screenshots"
```

**Organize by date:**
```bash
export AUTO_SNAP_USE_DATE_SUBDIRS=true
export AUTO_SNAP_INCLUDE_TIMESTAMP=true
```

**Custom file names:**
```bash
export AUTO_SNAP_FILE_NAME_TEMPLATE="doc_{page:04d}"
```

## 🌍 Multiple Languages

**Add more OCR languages:**
```bash
sudo apt install tesseract-ocr-spa  # Spanish
sudo apt install tesseract-ocr-fra  # French
sudo apt install tesseract-ocr-deu  # German
```

Then tell Claude: *"Process this document in Spanish"*

## 🔐 Privacy

- Everything runs locally on your machine
- No cloud services or uploads
- Only captures what you ask for
- Automatic cleanup of temp files

---

**Ready to automate your screenshots?** Install Auto-Snap and start talking to your MCP Clients about your documents! 🚀