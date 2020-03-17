import errno
import utime
import mqtt

timer = machine.Timer(-1)
timer_end = 0

def topics(location, room, typ, name):
    args = (location, room, typ, name)
    topics = ['/'.join((location, room, typ, name))]
    for i in range(1, 4):
        topics.append('/'.join(args[:i]) + '/global')
    return topics

def callback(client, userdata, message):
    topic = message.topic
    msg = message.payload
    if not msg:
        return
    _, command = topic.rsplit('/', 1)
    if command == 'webrepl':
        if msg == 'ON':
            print('REPL ON')
            web_repl()
        if msg == 'OFF':
            print('REPL OFF')
            web_repl(stop=True)
    elif command == 'set':
        if msg == 'ON':
            POWER_ON()
        elif msg == 'OFF':
            POWER_OFF()
            timer.deinit()
            global timer_end
            timer_end = 0
    elif command == 'set_timer':
        period = int(msg) * 3600
        global timer_end
        timer_end = utime.time() + period
        if period > 0:
            POWER_ON()
            timer.init(period=period * 1000,
                       mode=timer.ONE_SHOT,
                       callback=lambda t: POWER_OFF(publish=True))
        else:
            timer.deinit()
            # Resubscribe to `<topic>/set` to reset to desired state
            client.subscribe(topic[:-6], qos=1)

def subscribe(client, root_topics):
    for topic in root_topics:
        client.subscribe(topic+'/set', qos=1)
        client.subscribe(topic+'/set_timer', qos=1)
        client.subscribe(topic+'/webrepl', qos=1)

def publish_state(client, root_topic, toggle=False):
    if RELAY.value():
        msg = 'ON'
    else:
        msg = 'OFF'
    client.publish(root_topic, msg, retain=True)
    if toggle:
        client.publish(root_topic+'/set', msg, retain=True)

def publish_timer(client, root_topic):
    topic = root_topic + '/timer'
    remaining = timer_end - utime.time()
    if remaining > 0:
        msg = '{:.2f}'.format(remaining/3600)
    else:
        msg = '0'
    client.publish(topic, msg, retain=True)

def main():
    client = mqtt.Client(cfg['CLIENT_ID_PREFIX'] + hostname())
    client.connect(cfg['MQTT_HOST'], keepalive=60)
    client.clean_session = False
    client.on_message = callback
    mytopics = topics(cfg['LOCATION'], cfg['ROOM'], cfg['TYPE'], cfg['NAME'])
    root_topic = mytopics[0]
    while True:
        if not client.reconnect():
            subscribe(client, mytopics)
        while client.connected:
            try:
                ping = client.loop_read()
                if not ping:
                    client.ping()
                publish_state(client, root_topic, toggle=TOGGLED[0])
                TOGGLED[0] = False
                publish_timer(client, root_topic)
            except Exception:
                raise
        utime.sleep(10)
        web_repl()

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
    fail_mode()
