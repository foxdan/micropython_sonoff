import utime
import mqtt

def topics(location, room, typ, name):
    args = (location, room, typ, name)
    topics = ['/'.join((location, room, typ, name))]
    for i in range(1, 4):
        topics.append('/'.join(args[:i]) + '/global')
    return topics

def timer_power_off(userdata):
    userdata['timer'].deinit()
    userdata['timer_end'] = 0
    POWER_OFF()

def callback(client, userdata, message):
    print(message)
    topic, command = message.topic.rsplit('/', 1)
    timer = userdata['timer']
    if not message.payload:
        return
    if command == 'webrepl':
        if message.payload == 'ON':
            print('REPL ON')
            web_repl()
        elif message.payload == 'OFF':
            print('REPL OFF')
            web_repl(stop=True)
    elif command == 'set':
        if message.payload == 'ON':
            POWER_ON()
        elif message.payload == 'OFF':
            POWER_OFF()
        timer.deinit()
        userdata['timer_end'] = 0
    elif command == 'set_timer':
        period = int(float(message.payload) * 3600)
        if period > 0:
            POWER_ON()
            userdata['timer_start'] = utime.time()
            userdata['timer_end'] = utime.time() + period
            timer.init(period=period * 1000,
                       mode=timer.ONE_SHOT,
                       callback=lambda t: timer_power_off(userdata))
        else:
            timer.deinit()
            userdata['timer_end'] = 0
    elif command == 'suggest':
        print('AUTOMATION')
        if utime.time() - userdata['timer_start'] < 5:
            return
        if userdata['timer_end'] == 0:
            if message.payload == 'ON':
                POWER_ON()
                timer.init(period=30 * 60 * 1000,
                           mode=timer.ONE_SHOT,
                           callback=lambda t: POWER_OFF())
            elif message.payload == 'OFF':
                POWER_OFF()

def subscribe(client, root_topics):
    for topic in root_topics:
        client.subscribe(topic+'/webrepl', qos=1)
        for sub_topic in ('/set', '/set_timer', '/suggest'):
            client.publish(topic+sub_topic, retain=True)
            client.subscribe(topic+sub_topic, qos=1)

def publish_state(client, root_topic):
    telegraf_line = ('{TYPE},location={LOCATION},room={ROOM},name={NAME} '
                     'on=').format(**cfg)
    if RELAY.value():
        msg = 'ON'
        client.publish('telegraf', telegraf_line + '1')
        print('PUBLISH ON')
    else:
        msg = 'OFF'
        client.publish('telegraf', telegraf_line + '0')
        print('PUBLISH OFF')
    client.publish(root_topic, msg, retain=True)

def publish_timer(client, root_topic):
    topic = root_topic + '/timer'
    remaining = client.userdata['timer_end'] - utime.time()
    if remaining > 0:
        msg = '{:.2f}'.format(remaining/3600)
    else:
        client.userdata['timer_end'] = 0
        msg = '0'
    client.publish(topic, msg, retain=True)

def run(client):
    mytopics = topics(cfg['LOCATION'], cfg['ROOM'], cfg['TYPE'], cfg['NAME'])
    if not client.reconnect():
        subscribe(client, mytopics)
    root_topic = mytopics[0]
    while client.connected:
        if not client.loop_read():
            client.ping()
            publish_state(client, root_topic)
            publish_timer(client, root_topic)
        fail_mode(False)

def main():
    POWER_OFF()
    userdata = {
        'timer': machine.Timer(-1),
        'timer_end': 0,
        'timer_start': utime.time(),
    }
    client = mqtt.Client(cfg['CLIENT_ID_PREFIX'] + hostname(),
                         clean_session=True,
                         userdata=userdata)
    client.host = cfg['MQTT_HOST']
    client.port = 1883
    client.keepalive = 60
    client.on_message = callback
    exception_count = 0
    while True:
        try:
            run(client)
        except KeyboardInterrupt:
            break
        except Exception as e:
            exception_count += 1
            print(e)
            if exception_count >= 3:
                print('Enabling fail because exceptions')
                fail_mode()
            if exception_count % 10 == 0:
                nw_config()
            utime.sleep(5)
        else:
            exception_count = 0

main()
