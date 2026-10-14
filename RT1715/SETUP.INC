; Fixed setup for the supplied DOSBox-X configuration.
; Same message layout as MAIN/START.C; 2 = SB Pro, quality 2 = 20 kHz.
        lds     bx,cs:msgareapnt
        mov     word ptr ds:[bx],0
        mov     word ptr ds:[bx+2],2
        mov     word ptr ds:[bx+4],2
        mov     word ptr ds:[bx+6],0 ; do not loop
        ; Avoid STMIK's timing-dependent ISA autodetection under emulation.
        mov     es,cs:stmikseg
        mov     es:_zoutputio,220h
        mov     es:_zoutputirq,7
        mov     es:_zoutputdma,1
