; MUSIC0 is already playing at order 18. Keep it running across all parts.
        mov     cs:notextmode,1
        mov     si,OFFSET exe19       ; VISU/C/U2E.C: city flyover
        call    partexecute
IFDEF RT_ROBOTRON
        mov     ah,4dh
        int     21h
        or      al,al
        jz      @@rt_flight_ok
        mov     cs:errorcode,8
        jmp     @@rt_sequence_done
@@rt_flight_ok:
ENDIF
IFNDEF RT_ROBOTRON
        mov     si,OFFSET exe2021     ; END/END.C: end logo / transition
        call    partexecute
ENDIF
        mov     si,OFFSET exe22       ; CREDITS/MAIN.C: illustrated cards
        call    partexecute
        ; Fall through to the original music fade and DOS cleanup.
IFDEF RT_CUSTOM_CREDITS
        mov     ah,4dh              ; propagate a failed custom credits load
        int     21h
        or      al,al
        jz      @@rt_credit_ok
        mov     cs:errorcode,8
@@rt_credit_ok:
ENDIF

IFDEF RT_ROBOTRON
@@rt_sequence_done:
ENDIF
