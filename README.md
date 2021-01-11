# MCUSim
Rad 7 till 60 innehåller det som cpu_pkg och instruktionsavkodaren gör, vilket kan justeras beroende på vad en specifik grupp valt.

File->Set Clock justerar vilken klocka som används [manual, automatisk ~1KHz]
File->Load program tar en .hex fil som gjorts av 'FPGA_ROM_Editor' som kom med labb 5 filerna
File->Reset MCU resetar output, stack, reg och pc

Knapparna förklarar sig själva, nertryckt = 1, normal = 0
Skrivet i Python3.8
