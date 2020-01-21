import os
import io
import time
import multiprocessing as mp
from queue import Empty
import picamera
from PIL import Image
from http import server
import socketserver
import numpy as np

HTML_PAGE="""\
<html>
<head>
<title>Face recognition</title>
</head>
<body>
<center><h1>Cam</h1></center>
<center><img src="streamLow.mjpg" width="640" height="480" /></center>
</body>
</html>
"""

class QueueOutput(object):
    def __init__(self, queue, finished):
        self.queue = queue
        self.finished = finished
        self.stream = io.BytesIO()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            # New frame, put the last frame's data in the queue
            size = self.stream.tell()
            if size:
                self.stream.seek(0)
                if self.queue.empty():
                    self.queue.put(self.stream.read(size))
                self.stream.seek(0)
        self.stream.write(buf)

    def flush(self):
        self.queue.close()
        self.queue.join_thread()
        self.finished.set()

def do_capture(queueHiRes, finishedHires, queueLoRes, finishedLores):
    print('Capture started')
    with picamera.PiCamera(sensor_mode=2) as camera:
        camera.resolution=(1920,1080)
        camera.framerate=15
        camera.video_stabilization = True
        camera.video_denoise = True
        camera.vflip = True
        camera.sharpness = 0
        camera.meter_mode = 'backlit'
        camera.exposure_compensation = 7
        print(camera.revision)
        outputHiRes = QueueOutput(queueHiRes, finishedHires)
        outputLoRes = QueueOutput(queueLoRes, finishedLores)
        camera.start_recording(outputHiRes, format='mjpeg', quality=80)
        camera.start_recording(outputLoRes, splitter_port=2, format='mjpeg', resize=(640,480))
        camera.wait_recording(100)
        #camera.wait_recording(100,splitter_port=2)
        camera.stop_recording(splitter_port=2)
        camera.stop_recording()
        time.sleep(0.2)
        camera.close()

def do_processing_hires(queue, queueout, finished):
    st = time.monotonic()
    cnt = 1
    fps = 0
    frameSkip = 12
    while not finished.wait(0):
        try:
            stream = io.BytesIO(queue.get(False))
        except Empty:
            pass
        else:
            if cnt >= 20:
                fps = cnt/(time.monotonic()-st)
                st = time.monotonic()
                cnt = 1
                print('%d: Processing image with size %dx%d at %dFPS' % (
                    os.getpid(), 1920, 1080, fps))# image.size[0], image.size[1], fps))
            else:
                cnt += 1
            stream.seek(0)
            #image = Image.open(stream)
            frameSkip -= 1
            if frameSkip <= 0:
                frameSkip = 1
                if queueout.empty():
                    #queueout.put(image)
                    queueout.put(stream)
            # Pretend it takes 0.1 seconds to process the frame; on a quad-core
            # Pi this gives a maximum processing throughput of 40fps
            #time.sleep(0.1)

def do_processing_lores(queue, queueout, finished):
    st = time.monotonic()
    cnt = 1
    fps = 0
    while not finished.wait(0):
        try:
            stream = io.BytesIO(queue.get(False))
        except Empty:
            pass
        else:
            #print('Start {0:.3f}'.format(time.monotonic()))
            if cnt >= 20:
                fps = cnt/(time.monotonic()-st)
                st = time.monotonic()
                cnt = 1
                print('%d: Processing image with size %dx%d at %dFPS' % (
                    os.getpid(), image.size[0], image.size[1], fps))
            else:
                cnt += 1
            stream.seek(0)
            image = Image.open(stream)
            props=[]
            for i in range(5):
                prop = {'coord': (0.1, 0.1*i, 0.1, 0.1*i), 'type': 15}
                props.append(prop)
            if queueout.empty():
                queueout.put((image, props))
            # Pretend it takes 0.1 seconds to process the frame; on a quad-core
            # Pi this gives a maximum processing throughput of 40fps
            #time.sleep(0.1)

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
  #      if self.path == '/':
  #          self.send_response(301)
  #          self.send_header('Location', '/index.html')
  #          self.end_headers()
  #      elif self.path == '/index.html':
  #          stri = HTML_PAGE
  #          content = stri.encode('utf-8')
  #          self.send_response(200)
  #          self.send_header('Content-Type', 'text/html')
  #          self.send_header('Conent-Length', len(content))
  #          self.end_headers()
  #          self.wfile.write(content)
        # elif self.path == '/data.html':
        #     stri = coral_engine.result_str
        #     content = stri.encode('utf-8')
        #     self.send_response(200)
        #     self.send_header('Content-Type', 'text/html')
        #     self.send_header('Conent-Length', len(content))
        #     self.end_headers()
        #     self.wfile.write(content)
   #     elif self.path == '/streamLow.mjpg':
        if self.path == '/streamLow.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            strprops = ''
            try:
                while True:
                    if not self.server.Queue.empty():
                        t0 = time.monotonic()
                        frame = self.server.Queue.get(False)
                        t1 = time.monotonic()
                        #print('Convert')
                        #ret, buf = cv2.imencode('.jpg', frame)
                        if self.server.format == 'JPEG':
                            buf = frame
                        else:
                            buf = io.BytesIO()
                            (img, props) = frame
                            strprops = ''
                            for prop in props:
                                strprops += 'Coord = ({0:.4f}, {1:.4f}, {2:.4f}, {3:.4f}). Class = {4:d}\n'.format(prop['coord'][0],
                                                                                                                   prop['coord'][1],
                                                                                                                   prop['coord'][2],
                                                                                                                   prop['coord'][3],
                                                                                                                   prop['type'])
                            img.save(buf, format='JPEG', subsampling=0, quality=80)
                        t2 = time.monotonic()
                        self.wfile.write(b'-FRAME\r\n')
                        self.send_header('Content-Type', 'image/jpeg')
                        lines=[]
                        self.send_header('Content-Length', len(buf.getvalue()))
                        self.end_headers()
                        t3 = time.monotonic()
                        self.wfile.write(buf.getvalue())
                        if self.server.format == 'RAW':
                            self.wfile.write(bytes(strprops, 'utf8'))
                            self.wfile.write(b'\xff\xaa\xee')
                        self.wfile.write(b'\r\r')
                        t4 = time.monotonic()
                        #print('{0:.1f}ms {1:.1f}ms {2:.1f}ms {3:.1f}ms {4:.1f}ms'.format((t1-t0)*1000, (t2-t1)*1000, (t3-t2)*1000, (t4-t3)*1000, (t4-t0)*1000))
                        #print('End {0:.3f}'.format(t4))
            except Exception as e:
                print('Removed streaming clients %s: %s', self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

def server_start(frameQueue, port, format, servstop):
    try:
        address = ('', port)
        server = StreamingServer(address, StreamingHandler)
        server.Queue = frameQueue
        server.format = format
        print('Started server')
        server.serve_forever()
    finally:
        # Release handle to the webcam
        servstop.set()

if __name__ == '__main__':
    queueHiRes = mp.Queue(1)
    finishedHiRes = mp.Event()
    queueLoRes = mp.Queue(1)
    queueProcessedLow = mp.Queue(1)
    queueProcessedHigh = mp.Queue(1)
    finishedLoRes = mp.Event()
    ServerStop = mp.Event()
    capture_proc = mp.Process(target=do_capture, args=(queueHiRes, finishedHiRes, queueLoRes, finishedLoRes), daemon=True)
    #processing_procs = [
    #    mp.Process(target=do_processing, args=(queue, finished))
    #    for i in range(1)
    #    ]
    proccessing_proc_hires = mp.Process(target=do_processing_hires, args=(queueHiRes, queueProcessedHigh, finishedHiRes), daemon=True)
    proccessing_proc_lores = mp.Process(target=do_processing_lores, args=(queueLoRes, queueProcessedLow, finishedLoRes), daemon=True)
    serverProc = mp.Process(target=server_start, args=(queueProcessedLow, 8000, 'RAW', ServerStop), daemon=True)
    serverProc2 = mp.Process(target=server_start, args=(queueProcessedHigh, 8001, 'JPEG', ServerStop), daemon=True)
    serverProc.start()
    serverProc2.start()
    #for proc in processing_procs:
    #    proc.start()
    proccessing_proc_hires.start()
    proccessing_proc_lores.start()
    capture_proc.start()
    #for proc in processing_procs:
    #    proc.join()
    #proccessing_proc_hires.join()
    #proccessing_proc_lores.join()
    #capture_proc.join()
    while True:
        if finishedHiRes.is_set() or finishedLoRes.is_set():
            finishedLoRes.set()
            finishedHiRes.set()
            time.sleep(0.1)
            serverProc.terminate()
            serverProc2.terminate()
            proccessing_proc_hires.terminate()
            proccessing_proc_lores.terminate()
            capture_proc.terminate()
            break
        time.sleep(1)
    
