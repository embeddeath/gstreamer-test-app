# Qualcomm Linux EVK Camera Streaming Setup

This document outlines the step-by-step process used to identify the camera device, determine its supported pixel formats, and build a lightweight HTTP-based MJPEG streaming pipeline between a Qualcomm Linux EVK and a Windows host PC.

## 1. Camera Device Discovery and Format Determination

To locate the active camera sensor node on the Qualcomm board and verify its output formats:

### 1.1 Identify Video Device Nodes

List all available V4L2 video capture devices on the Linux target:

```bash
v4l2-ctl --list-devices
```

Or list devices under `/dev`:

```bash
ls -l /dev/video*
```

The active video device nodes created by the V4L2 kernel driver are stored directly under `/dev/video*` (for example `/dev/video0`, `/dev/video1`, `/dev/video2`, etc.).

### 1.2 Query Device Capabilities and Pixel Formats

Inspect each video node to determine which one corresponds to the physical camera hardware and supports JPEG encoding:

```bash
v4l2-ctl --device=/dev/video2 --list-formats-ext
```

> Key finding: `/dev/video2` was identified as the active video input node, natively exposing MJPG / `image/jpeg` compressed streams at 1280x720 resolution at 30 FPS.

## 2. Windows Receiver Setup (Python Flask)

Because WSL/Hyper-V network isolation can block raw incoming UDP streams, an HTTP POST ingest server was deployed on the Windows host. The server receives raw JPEG buffers from the board via `POST /upload` and streams them to any web browser using an MJPEG multipart response (`multipart/x-mixed-replace`).

### Dependencies (Windows Host)

```bash
pip install flask pillow
```

### Script: `camera_stream.py`

Save and run the following script on the Windows host at `192.168.0.179`:

```python
import time

from flask import Flask, Response, request, render_template_string, jsonify

app = Flask(__name__)

# Holds the latest raw frame bytes sent from the EVK
latest_frame = None


@app.route('/upload', methods=['POST'])
def upload():
    global latest_frame

    if request.data:
        latest_frame = request.data
        return jsonify({"status": "ok"}), 200

    return jsonify({"error": "No data received"}), 400


def generate_mjpeg():
    global latest_frame

    while True:
        if latest_frame is not None:
            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + latest_frame + b'\r\n'
            )
            time.sleep(0.033)  # ~30 FPS
        else:
            time.sleep(0.1)  # Wait briefly for the first frame to arrive


@app.route('/video_feed')
def video_feed():
    response = Response(
        generate_mjpeg(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

    # Prevent browser caching of the video stream connection
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response


@app.route('/')
def index():
    html_content = """
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Qualcomm EVK Camera Stream</title>
        <style>
            body {
                background: #121212;
                color: #fff;
                font-family: sans-serif;
                text-align: center;
                margin-top: 40px;
            }

            .stream-container {
                display: inline-block;
                border: 2px solid #333;
                border-radius: 8px;
                overflow: hidden;
            }

            img {
                display: block;
                max-width: 100%;
                height: auto;
            }
        </style>
    </head>
    <body>
        <h1>Qualcomm EVK Camera Stream</h1>
        <div class="stream-container">
            <img src="/video_feed" alt="Live camera stream">
        </div>
    </body>
    </html>
    """

    return render_template_string(html_content)


if __name__ == '__main__':
    print("Starting Receiver Server on port 5000...")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
```

Run the server on Windows:

```bash
python camera_stream.py
```

## 3. Sender Setup (Qualcomm EVK Bash Streamer)

On the Qualcomm EVK target, a Bash script captures individual JPEG frames using `gst-launch-1.0` from `/dev/video2` and transmits them via `curl` binary HTTP POST requests to the Windows receiver.

### Script: `~/stream.sh`

Create and deploy the stream loop on the Qualcomm board:

```bash
cat << 'EOF' > ~/stream.sh
#!/bin/bash

while true; do
    # Capture 1 frame to a temporary file
    gst-launch-1.0 v4l2src device=/dev/video2 num-buffers=1 ! image/jpeg,width=1280,height=720 ! filesink location=/tmp/frame.jpg > /dev/null 2>&1

    # Ensure the file exists and is greater than 0 bytes before sending
    if [ -s /tmp/frame.jpg ]; then
        curl -s -X POST -H "Content-Type: image/jpeg" --data-binary @/tmp/frame.jpg http://192.168.0.179:5000/upload
    fi

    sleep 0.03
done
EOF

chmod +x ~/stream.sh
```

Execute the streamer on the EVK:

```bash
~/stream.sh
```

## 4. Verification and Usage

1. Start the Python receiver by running:

   ```bash
   python camera_stream.py
   ```

2. Start the board streamer by running:

   ```bash
   ~/stream.sh
   ```

3. Open a browser and navigate to:

   - `http://localhost:5000`
   - [http://192.168.0.179:5000](http://192.168.0.179:5000)

4. Result: The web browser displays the live 1280x720 camera feed in real time without firewall or socket configuration issues.