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