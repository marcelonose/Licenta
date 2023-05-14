import machine
import uasyncio
import utime
import queue

# Settings
led = machine.Pin("LED", machine.Pin.OUT)
btn = machine.Pin(15, machine.Pin.IN, machine.Pin.PULL_UP)

# Coroutine: blink on a timer
async def blink(q):
    delay_ms = 0 
    while True:
        if not q.empty():
            delay_ms = await q.get()
        led.toggle()
        await uasyncio.sleep_ms(delay_ms)
        
# Coroutine: only return on button press
async def wait_button():
    btn_prev = btn.value()
    while (btn.value() == 1) or (btn.value() == btn_prev): #buton neapasat - 1, buton apasat -0
        btn_prev = btn.value()
        await uasyncio.sleep(0.04)
        
# Coroutine: entry point for asyncio program
async def main():
    
    # Queue for passing messages
    q = queue.Queue()
    
    # Start coroutine as a task and immediately return
    uasyncio.create_task(blink(q))
    
    # Main loop
    timestamp = utime.ticks_ms()
    while True:
        
        # Calculate time between button presses
        await wait_button()
        new_time = utime.ticks_ms()
        delay_time = new_time - timestamp
        timestamp = new_time
        print(delay_time)
        
        # Send calculated time to blink task
        delay_time = min(delay_time, 2000)
        await q.put(delay_time)
    
# Start event loop and run entry point coroutine
uasyncio.run(main())