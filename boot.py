# This file is executed on every boot (including wake-boot from deepsleep)
#import esp
#esp.osdebug(None)
import uos, machine
#uos.dupterm(None, 1) # disable REPL on UART(0)
import gc
import ujson
import network
import utime
import micropython
AP_IF = network.WLAN(network.AP_IF)
gc.collect()
LED = machine.PWM(machine.Pin(13), duty=500, freq=2)
RELAY = machine.Signal(12, machine.Pin.OUT)
BUTTON = machine.Pin(0, machine.Pin.IN)
REPL = bytearray((False,))
#machine.freq(160000000)

try:
    with open('cfg.json', 'r') as jcfg:
        cfg = ujson.load(jcfg)
except Exception as e:
    cfg = dict()

def POWER_ON(publish=False):
    print("POWER ON")
    RELAY.on()
    LED.duty(900)

def POWER_OFF(publish=False):
    print("POWER OFF")
    RELAY.off()
    LED.duty(1020)

def debounce_press(_):
    utime.sleep_ms(10)
    for _ in range(10):
        utime.sleep_ms(5)
        if BUTTON.value():
            break
    else:
        if RELAY.value():
            POWER_OFF(publish=True)
        else:
            POWER_ON(publish=True)

last_press = 0
def button_hdlr(_pin):
    global last_press
    state = machine.disable_irq()
    if utime.time() - last_press > 1:
        last_press = utime.time()
        micropython.schedule(debounce_press, 0)
    machine.enable_irq(state)
BUTTON.irq(handler=button_hdlr, trigger=(BUTTON.IRQ_FALLING), hard=True)

def web_repl(stop=False):
    import webrepl
    if stop:
        webrepl.stop()
        REPL[0] = False
        return
    if not REPL[0]:
        webrepl.start(password=cfg.get('DEBUG_PASS', 'python'))
        REPL[0] = True
web_repl()

def save_cfg():
    with open('cfg.json', 'w') as jcfg:
        ujson.dump(cfg, jcfg)

def hostname():
    try:
        name = '{}_{}_{}'.format(cfg['ROOM'], cfg['TYPE'], cfg['NAME'])
    except KeyError:
        import network, ubinascii
        mac_end = network.WLAN(network.AP_IF).config('mac')[-3:]
        name = 'pyiot-' + ubinascii.hexlify(mac_end).decode('utf')
    return name

def fail_mode(enable=True):
    if enable:
        if AP_IF.active():
            return
        LED.freq(3)
        AP_IF.active(True)
        AP_IF.config(essid=hostname(),
                     password='homebrewiot',
                     authmode=network.AUTH_WPA2_PSK,
                     channel=11)
        web_repl()
        return
    if AP_IF.active():
        AP_IF.active(False)
    LED.freq(500)

def nw_config():
    import utime
    LED.freq(1)
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.scan()
    wlan.config(dhcp_hostname=hostname())
    wlan.connect(cfg['SSID'], cfg['PASSWORD'])
    timeout = utime.time() + 30
    while not wlan.isconnected():
        if utime.time() > timeout:
            return False
    import ntptime
    ntptime.host = cfg.get('NTP_SERVER') or ntptime.host
    for i in range(5):
        utime.sleep((ord(uos.urandom(1)) / 256) * (1 << i))
        try:
            ntptime.settime()
        except Exception:
            pass
        else:
            break
    AP_IF.active(False)
    LED.freq(500)
    return True

try:
    if not nw_config():
        fail_mode()
except Exception as e:
    print(e)
    fail_mode()
    raise
