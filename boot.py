# This file is executed on every boot (including wake-boot from deepsleep)
#import esp
#esp.osdebug(None)
import uos, machine
#uos.dupterm(None, 1) # disable REPL on UART(0)
import gc
import ujson
gc.collect()
LED = machine.PWM(machine.Pin(13, machine.Pin.OUT), duty=500, freq=2)
RELAY = machine.Signal(12, machine.Pin.OUT)
BUTTON = machine.Pin(0, machine.Pin.IN)
TOGGLED = bytearray((False,))
REPL = bytearray((False,))
machine.freq(160000000)

try:
    with open('cfg.json', 'r') as jcfg:
        cfg = ujson.load(jcfg)
except Exception as e:
    cfg = dict()

def POWER_ON(publish=False):
    print("POWER ON")
    RELAY.on()
    LED.duty(900)
    if publish:
        TOGGLED[0] = True

def POWER_OFF(publish=False):
    print("POWER OFF")
    RELAY.off()
    LED.duty(1020)
    if publish:
        TOGGLED[0] = True

def button_hdlr(_pin):
    state = machine.disable_irq()
    if RELAY.value():
        POWER_OFF(publish=True)
    else:
        POWER_ON(publish=True)
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

def fail_mode():
    import network
    import ubinascii
    ap = network.WLAN(network.AP_IF)
    if ap.active():
        return
    LED.freq(3)
    network.WLAN(network.STA_IF).active(False)
    ap.active(True)
    ap.config(essid=hostname(),
              password='homebrewiot',
              authmode=network.AUTH_WPA2_PSK,
              channel=11)
    web_repl()

def nw_config():
    import network
    import utime
    LED.freq(1)
    network.WLAN(network.AP_IF).active(False)
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.config(dhcp_hostname=hostname())
    wlan.connect(cfg['SSID'], cfg['PASSWORD'])
    timeout = utime.time() + 30
    while True:
        if wlan.isconnected():
            import ntptime
            ntptime.host = 'ie.pool.ntp.org'
            for i in range(4):
                utime.sleep(i << 1)
                try:
                    ntptime.settime()
                except Exception:
                    pass
                else:
                    break
            LED.freq(500)
            return True
        elif utime.time() > timeout:
            return False

try:
    if not nw_config():
        fail_mode()
except Exception as e:
    print(e)
    fail_mode()
