import cv2
import urllib 
import numpy as np
import multiprocessing as mp

stream = 'http://192.168.53.114:8000/streamLow.mjpg'
stream2 = 'http://192.168.53.114:8001/streamLow.mjpg'

def procImg(str, wind, stop):
    bytes = ''
    stream = urllib.urlopen(str)
    while not stop.is_set():
        try:
            bytes += stream.read(4096)
            a = bytes.find('\xff\xd8')
            b = bytes.find('\xff\xd9')
            if wind == 'Low':
                c = bytes.find('\xff\xaa\xee')
            if a != -1 and b != -1:
                jpg = bytes[a:b+2]
                if wind == 'Low':
                    if c != -1:
                        str = bytes[b+2:c]
                        print(str)
                        bytes = bytes[c+3:]
                    else:
                        bytes = bytes[b+2:]
                else:
                    bytes = bytes[b+2:]
                i = cv2.imdecode(np.fromstring(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                cv2.imshow(wind, i)
                cv2.waitKey(1)
            if cv2.waitKey(1) == ord('q'):
                stop.set()
                break
        except:
            pass
if __name__ == '__main__':
    st = mp.Event()
    lowProc = mp.Process(target = procImg, args=(stream, 'Low', st))
    HighProc = mp.Process(target = procImg, args=(stream2, 'High', st))
    lowProc.start()
    HighProc.start()
    lowProc.join()
    HighProc.join()
    exit(0)
