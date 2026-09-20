#!/bin/bash
while true; do
  # Capture 1 frame to a temporary file
  gst-launch-1.0 v4l2src device=/dev/video2 num-buffers=1 ! image/jpeg,width=128

  # Ensure the file exists and is greater than 0 bytes before sending
  if [ -s /tmp/frame.jpg ]; then
    curl -s -X POST -H "Content-Type: image/jpeg" --data-binary @/tmp/frame.jpg
  fi

  sleep 0.03
done
