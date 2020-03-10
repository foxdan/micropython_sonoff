import errno
import utime
from umqtt.simple import MQTTClient

timer = machine.Timer(-1)
timer_end = 0

def topics(location, room, typ, name):
    args = (location, room, typ, name)
    topics = ['/'.join((location, room, typ, name))]
    for i in range(1, 4):
        topics.append('/'.join(args[:i]) + '/global')
    return topics

def callback(topic, msg):
    if not msg:
        return
    _, command = topic.rsplit(b'/', 1)
    if command == b'webrepl':
        if msg == b'ON':
            print('REPL ON')
            web_repl()
        if msg == b'OFF':
            print('REPL OFF')
            web_repl(stop=True)
    elif command == b'set':
        if msg == b'ON':
            POWER_ON()
        elif msg == b'OFF':
            POWER_OFF()
    elif command == b'set_timer':
        period = int(msg) * 3600
        global timer_end
        timer_end = utime.time() + period
        if period > 0:
            POWER_ON()
            timer.init(period=period * 1000,
                       mode=timer.ONE_SHOT,
                       callback=lambda t: POWER_OFF())
        else:
            timer.deinit()

client = MQTTClient(cfg['CLIENT_ID_PREFIX'] + hostname(),
                    cfg['MQTT_HOST'], keepalive=60)
client.cb = callback

def connect(clean=False):
    if client.sock:
        client.sock.close()
    while True:
        try:
            session_resume = client.connect(clean)
        except Exception as e:
            web_repl()
            print(e)
            utime.sleep(10)
        else:
            return session_resume

def subscribe(root_topics):
    for topic in root_topics:
        client.subscribe(topic+'/set', qos=1)
        client.subscribe(topic+'/set_timer', qos=1)
        client.subscribe(topic+'/webrepl', qos=1)

def publish_state(root_topic, toggle=False):
    if RELAY.value():
        msg = b'ON'
    else:
        msg = b'OFF'
    client.publish(root_topic, msg, retain=True)
    if toggle:
        client.publish(root_topic+'/set', msg, retain=True)

def publish_timer(root_topic):
    topic = root_topic + '/timer'
    remaining = timer_end - utime.time()
    if remaining > 0:
        msg = '{:.2f}'.format(remaining/3600)
    else:
        msg = '0'
    client.publish(topic, msg, retain=True)

def main():
    mytopics = topics(cfg['LOCATION'],
                      cfg['ROOM'],
                      cfg['TYPE'],
                      cfg['NAME'])
    root_topic = mytopics[0]
    connect(clean=True)
    subscribe(mytopics)
    last_ping = utime.time()
    while True:
        try:
            client.sock.settimeout(5)
            client.wait_msg()
        except OSError as e:
            if e.args[0] == errno.ETIMEDOUT:
                print("noop")
                if utime.time() - last_ping > 30:
                    print("ping")
                    publish_state(root_topic, toggle=TOGGLED[0])
                    TOGGLED[0] = False
                    publish_timer(root_topic)
                    #client.ping()
                    last_ping = utime.time()
            else:
                print(e)
                print("reconnect")
                if not connect(clean=False):
                    subscribe(mytopics)

try:
    main()
except KeyboardInterrupt:
    pass
except Exception as e:
    print(e)
    with open('exception.log', 'a') as elog:
        ttup = utime.localtime()
        datestr = '{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d} '.format(*ttup[:6])
        elog.write(datestr)
        elog.write(str(e))
        elog.write('\n')
    #fail_mode()
