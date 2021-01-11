import tkinter as tk
import tkinter.filedialog as fd
import os
import threading
import time


STACK_OP_POP = '10'
STACK_OP_PUSH = '01'
STACK_OP_HOLD = '00'

ADDR_PC_PLUS_ONE = '00'
ADDR_TOS = '01'
ADDR_DATA = '10'
ADDR_DATA_PC_Z = '11'   # a shortcut made to allow for a full decoding of an OPCODE before calculating Z with the alu

ALUSRC_INPUT = '0'
ALUSRC_REG = '1'

ALUOP_APB = '010'
ALUOP_AMB = '011'
ALUOP_A = '000'
ALUOP_B = '001'
ALUOP_AANDB = '100'
ALUOP_AXB = '110'
ALUOP_0 = '111'

codeToName = {
    '0000': 'CALL',
    '0001': 'RET',
    '0010': 'BZ',
    '0011': 'B',
    '0100': 'ADD',
    '0101': 'SUB',
    '0110': 'AND',
    '0111': 'LD',
    '1000': 'OUT',
    '1001': 'IN',
    '1010': 'DOUT',
    '1011': 'XOR',
    '1100': 'IN_XOR'
}


def getCode(OPCODE):
    decoder = {
        'CALL': STACK_OP_PUSH + ADDR_DATA + ALUOP_0 + ALUSRC_REG + '0' + '0',
        'RET': STACK_OP_POP + ADDR_TOS + ALUOP_0 + ALUSRC_REG + '0' + '0',
        'BZ': STACK_OP_HOLD + ADDR_DATA_PC_Z + ALUOP_B + ALUSRC_REG + '0' + '0',
        'B': STACK_OP_HOLD + ADDR_DATA + ALUOP_0 + ALUSRC_REG + '0' + '0',
        'ADD': STACK_OP_HOLD + ADDR_PC_PLUS_ONE + ALUOP_APB + ALUSRC_REG + '1' + '0',
        'SUB': STACK_OP_HOLD + ADDR_PC_PLUS_ONE + ALUOP_AMB + ALUSRC_REG + '1' + '0',
        'AND': STACK_OP_HOLD + ADDR_PC_PLUS_ONE + ALUOP_AANDB + ALUSRC_REG + '1' + '0',
        'LD': STACK_OP_HOLD + ADDR_PC_PLUS_ONE + ALUOP_A + ALUSRC_REG + '1' + '0',
        'OUT': STACK_OP_HOLD + ADDR_PC_PLUS_ONE + ALUOP_B + ALUSRC_REG + '0' + '1',
        'IN': STACK_OP_HOLD + ADDR_PC_PLUS_ONE + ALUOP_B + ALUSRC_INPUT + '1' + '0',
        'DOUT': STACK_OP_HOLD + ADDR_PC_PLUS_ONE + ALUOP_A + ALUSRC_REG + '0' + '1',
        'XOR': STACK_OP_HOLD + ADDR_PC_PLUS_ONE + ALUOP_AXB + ALUSRC_REG + '1' + '0',
        'IN_XOR': STACK_OP_HOLD + ADDR_PC_PLUS_ONE + ALUOP_AXB + ALUSRC_INPUT + '1' + '0'
    }
    return decoder[codeToName[''.join(OPCODE)]]


def bitWiseXOR(a, b):
    res = ''
    for i in range(len(a)):
        if a[i] == b[i]:
            res += '0'
        else:
            res += '1'
    return res, '1' not in res


def bitWiseAND(a, b):
    res = ''
    for i in a:
        for j in b:
            if i == '1' and j == '1':
                res += '1'
            else:
                res += '0'
    return res, '1' not in res


def pushStack(x, mcu):
    for i in reversed(range(1, len(mcu.stack))):
        mcu.stack[i] = mcu.stack[i - 1]
    mcu.stack[0] = x


def popStack(x, mcu):
    popped = mcu.stack[-1]
    for i in range(len(mcu.stack), len(mcu.stack) - 1):
        mcu.stack[i] = mcu.stack[i + 1]
    mcu.stack[-1] = '0' * 8
    return popped


def fromStringToInt(s):
    return int(s, 2)


def fromIntToString(i, size=8):
    return bin(i)[2:].zfill(size)[-size:]


def setReg(DEST, x, RegEna, mcu):
    if DEST == '0':
        if RegEna == '1':
            mcu.reg0 = x
    else:
        if RegEna == '1':
            mcu.reg1 = x


def twosComp(binaryString):
    res = ''
    for i in list(binaryString):
        if i == '0':
            res += '1'
        else:
            res += '0'
    return MCU.alu['010'](res, '00000001')[0][-8:]


class MCU:
    dataLock = threading.Lock()
    INPUTDATA = '0' * 8
    OUTPUTDATA = '00000000'
    stackOp = {
        '00': lambda x, y: x,
        '01': pushStack,
        '10': popStack
    }
    alu = {
        '010': lambda a, b: (
            fromIntToString(fromStringToInt(a) + fromStringToInt(b)), fromStringToInt(a) + fromStringToInt(b) == 0),
        '011': lambda a, b: MCU.alu['010'](twosComp(a), b),
        '000': lambda a, b: (a, a == '00000000'),
        '001': lambda a, b: (b, b == '00000000'),
        '100': bitWiseAND,
        '110': bitWiseXOR,
        '111': lambda a, b: ('0' * 8, 1)
    }

    def __init__(self, addressCache=[]):
        self.pc = 0
        self.addressCache = addressCache
        while len(self.addressCache) < 64:
            self.addressCache.append('0000000000000')
        assert len(self.addressCache) <= 64
        self.reg0 = '0' * 8
        self.reg1 = '0' * 8
        self.stack = ['0' * 8] * 4

    def reset(self):
        with MCU.dataLock:
            self.pc = 0
            MCU.OUTPUTDATA = '00000000'
        self.reg0 = '0' * 8
        self.reg1 = '0' * 8
        self.stack = ['0' * 8] * 4

    def useProgram(self, addressCache=[]):
        self.addressCache = addressCache
        while len(self.addressCache) < 64:
            self.addressCache.append('0000000000000')

    def runClock(self):
        with MCU.dataLock:
            currentpc = self.pc
        addr = self.addressCache[currentpc]
        OPCODE = addr[0:4]
        DEST = addr[4]
        DATA = ''.join(addr[5:])

        fullCode = getCode(OPCODE)
        StackOp = ''.join(fullCode[0:2])
        AddrSrc = ''.join(fullCode[2:4])
        ALUOp = ''.join(fullCode[4:7])
        ALUSrc = ''.join(fullCode[7])
        RegEna = ''.join(fullCode[8])
        OutEna = ''.join(fullCode[9])

        if DEST == '0':
            currentRegData = self.reg0
        else:
            currentRegData = self.reg1
        with MCU.dataLock:
            currentInputData = MCU.INPUTDATA

        res, z = MCU.alu[ALUOp](DATA, (currentRegData if ALUSrc == ALUSRC_REG else currentInputData))
        setReg(DEST, res, RegEna, self)
        if OutEna == '1':
            MCU.OUTPUTDATA = res
        topOfStack = self.stack[0]
        MCU.stackOp[StackOp](fromIntToString(self.pc + 1), self)

        nextPc = currentpc

        if AddrSrc == ADDR_DATA_PC_Z:
            if z == 1:
                nextPc = int(DATA, 2)
            else:
                nextPc += 1

        elif AddrSrc == ADDR_DATA:
            nextPc = int(DATA, 2)
        elif AddrSrc == ADDR_TOS:
            nextPc = int(topOfStack, 2)
        elif AddrSrc == ADDR_PC_PLUS_ONE:
            nextPc += 1
        with MCU.dataLock:
            self.pc = nextPc


class ToggleButton(tk.Button):
    def __init__(self, listener=None, **kw):
        super().__init__(**kw)
        self.baseColor = self.cget('bg')
        self.val = False
        self.config(command=lambda: self.switch())
        self.listener = listener

    def switch(self):
        self.val = not self.val
        print(os.name)
        if os.name == 'nt':
            if self.val:
                self.config(relief=tk.SUNKEN)
            else:
                self.config(relief=tk.RAISED)
        else:
            if self.val:
                self.config(bg='blue')
            else:
                self.config(bg=self.baseColor)
            
        if self.listener:
            self.listener()


class MCUGui(tk.Tk):

    def __init__(self, mcu, clock):
        super().__init__()
        self.mcu = mcu
        self.clock = clock

        self.config(bg='#aaa')

        self.fps = 60
        self.lastOut = None
        self.latestInputData = None

        self.menuBar = tk.Menu(self, tearoff=0)
        self.fileMenu = tk.Menu(self.menuBar, tearoff=0)
        self.menuBar.add_cascade(label='File', menu=self.fileMenu)

        self.fileMenu.add_command(label='Load program', command=self.loadProgram)

        self.manualClockActive = tk.IntVar()

        self.clockMenu = tk.Menu(self.fileMenu, tearoff=0)
        self.clockMenu.add_radiobutton(label='Manual clock', value=False, variable=self.manualClockActive, command=self.changeClock)
        self.clockMenu.add_radiobutton(label='1 KHz clock', value=True, variable=self.manualClockActive, command=self.changeClock)

        self.fileMenu.add_cascade(label='Set clock', menu=self.clockMenu)

        self.fileMenu.add_command(label='Reset MCU', command=self.mcu.reset)

        self.config(menu=self.menuBar)

        self.output = tk.Label(self, text='OUTPUT\nNaN')
        self.pcDebug = tk.Label(self, text='PC_DEBUG\n0')

        self.trafficLightCanvas = tk.Canvas(self, width=200, height=200, highlightthickness=0)

        self.dayOrNight = ToggleButton(master=self, text='Day/Night', listener=self.updateInputMCU)
        self.carOnSideStreet = ToggleButton(master=self, text='Car on the side street', listener=self.updateInputMCU)
        self.g1 = ToggleButton(master=self, text='Sensor: G1', listener=self.updateInputMCU)
        self.g2 = ToggleButton(master=self, text='Sensor: G2', listener=self.updateInputMCU)
        self.lionCageOrTrafficLight = ToggleButton(master=self, text='Lion Cage Or Traffic Light', listener=self.updateInputMCU)

        self.output.grid(row=0, column=0, columnspan=2, padx=(10, 10), pady=(5, 5))
        self.pcDebug.grid(row=1, column=0, columnspan=2, padx=(10, 10), pady=(5, 5))

        self.dayOrNight.grid(row=0, column=2, padx=(10, 10), pady=(10, 10))
        self.carOnSideStreet.grid(row=1, column=2, padx=(10, 10), pady=(10, 10))

        self.g1.grid(row=0, column=3, padx=(10, 10), pady=(10, 10))
        self.g2.grid(row=1, column=3, padx=(10, 10), pady=(10, 10))

        self.lionCageOrTrafficLight.grid(row=3, column=0, columnspan=4, padx=(5, 5), pady=(5, 5))

        self.manualClock = tk.Button(text='Advance clock one step ->>>', command=self.mcu.runClock)
        self.manualClock.config(state=tk.NORMAL)
        self.manualClock.grid(row=4, column=0, columnspan=4, padx=(5, 5), pady=(5, 5))


        self.trafficLightCanvas.grid(row=0, column=4, rowspan=5)
        self.drawTrafficLights('00000000')

        self.manualClockActive.set(False)
        self.changeClock()
        self.after(1, self.updateGUIOutput)


    def changeClock(self):
        MCUClock.active = self.manualClockActive.get()
        if MCUClock.active:
            self.manualClock.config(state=tk.DISABLED)
        else:
            self.manualClock.config(state=tk.NORMAL)

    def updateInputMCU(self):
        inputData = ('0000' + str(int(self.g2.val)) + str(int(self.g1.val)) + str(int(self.carOnSideStreet.val)) + str(int(self.dayOrNight.val)))
        if not self.latestInputData or not self.latestInputData == inputData:
            with MCU.dataLock:
                MCU.INPUTDATA = inputData

        self.latestInputData = inputData

    def updateGUIOutput(self):

        with MCU.dataLock:
            pc = self.mcu.pc
            outputData = MCU.OUTPUTDATA

        self.pcDebug.config(text='PC_DEBUG:\n' + str(pc))

        if not self.lionCageOrTrafficLight.val:
            if self.lastOut:
                self.drawTrafficLights('00000000')
            self.output.config(text='OUTPUT:\n' + str(fromStringToInt(outputData)))
        else:
            if not self.lastOut:
                self.output.config(text='OUTPUT:\n')
            self.drawTrafficLights(outputData)

        self.lastOut = self.lionCageOrTrafficLight.val
        self.after(round(1000 * float(1)/self.fps), self.updateGUIOutput)

    def drawTrafficLights(self, code):
        c = self.trafficLightCanvas

        c.delete(tk.ALL)
        c.create_rectangle(0, 0, 200, 200, fill='#aaa')


        c.create_rectangle(10, 127, 36, 193, fill='black')

        c.create_oval(13, 130, 33, 150, fill='#888' if list(code)[7] == '0' else 'red')
        c.create_oval(13, 150, 33, 170, fill='#888' if list(code)[6] == '0' else 'yellow')
        c.create_oval(13, 170, 33, 190, fill='#888' if list(code)[5] == '0' else 'green')


        c.create_rectangle(127, 10, 193, 36, fill='black')

        c.create_oval(130, 13, 150, 33, fill='#888' if list(code)[4] == '0' else 'red')
        c.create_oval(150, 13, 170, 33, fill='#888' if list(code)[3] == '0' else 'yellow')
        c.create_oval(170, 13, 190, 33, fill='#888' if list(code)[2] == '0' else 'green')

    def loadProgram(self):
        file = fd.askopenfile(initialdir="./")
        program = []
        if file:
            if file.name.endswith('.txt'):
                for line in file:
                    currentLine = ''
                    for c in line:
                        if c == '0' or c == '1':
                            currentLine += c
                        elif c == '#':
                            break
                    if len(currentLine) == 13:
                        program.append(currentLine)
                self.mcu.useProgram(program)
            elif file.name.endswith('.hex'):
                for line in file:
                    program.append(fromIntToString(int(line[0:4], 16), 13))
                self.mcu.useProgram(program)


class MCUClock:
    active = False

    def __init__(self, mcu, freq):
        self.mcu = mcu
        self.freq = freq

    def run(self):
        startTime = time.time()
        while 1:
            if time.time() - startTime > float(1) / self.freq and MCUClock.active:
                self.mcu.runClock()
                startTime = time.time()


if __name__ == '__main__':
    mcu = MCU()
    clock = MCUClock(mcu, 1000)   # 1 kHz clock
    t = threading.Thread(target=clock.run)
    t.setDaemon(True)
    m = MCUGui(mcu, clock)

    t.start()

    m.mainloop()
