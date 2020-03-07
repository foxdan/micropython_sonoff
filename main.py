import errno
import utime
from umqtt.simple import MQTTClient

timer = machine.Timer(-1)

def callback(topic, msg):
    if topic == b'webrepl':
        if msg == b'ON':
            print('REPL ON')
            web_repl()
        if msg == b'OFF':
            print('REPL OFF')
            web_repl(stop=True)
    elif topic.startswith(cfg['TOPIC'].encode('utf')):
        sub_topics = topic.split(b'/')[2:]
        if not sub_topics:
            if msg == b'ON':
                POWER_ON()
            elif msg == b'OFF':
                POWER_OFF()
        else:
            if sub_topics[0] == b'timer':
                period = int(msg) * 1000 * 60 * 60
                if period > 0:
                    POWER_ON(publish=True)
                    timer.init(period=period,
                               mode=timer.ONE_SHOT,
                               callback=lambda t: POWER_OFF(publish=True))
                else:
                    timer.deinit()

client = MQTTClient(cfg['CLIENT_ID'], cfg['MQTT_HOST'], keepalive=60)
client.cb = callback

def connect():
    if client.sock:
        client.sock.close()
    while True:
        try:
            if not client.connect():
                print("subscribe")
                client.subscribe(cfg['TOPIC'] + '/#')
                client.subscribe('webrepl')
        except Exception as e:
            print("WTF")
            web_repl()
            print(e)
            utime.sleep(10)
        else:
            break

def publish_state():
    if RELAY.value():
        msg = b'ON'
    else:
        msg = b'OFF'
    client.publish(cfg['TOPIC'], msg, retain=True)

def main():
    connect()
    last_ping = utime.time()
    while True:
        try:
            if TOGGLED[0]:
                publish_state()
                TOGGLED[0] = False
            client.sock.settimeout(5)
            client.wait_msg()
        except OSError as e:
            if e.args[0] == errno.ETIMEDOUT:
                print("noop")
                if utime.time() - last_ping > 30:
                    print("ping")
                    client.ping()
                    last_ping = utime.time()
            else:
                print(e)
                print("reconnect")
                connect()

try:
    main()
except KeyboardInterrupt:
    pass
except Exception as e:
    print(e)
    #fail_mode()
