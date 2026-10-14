; MUSIC0 is already playing at order 18. Keep it running across all parts.
        mov     cs:notextmode,1
        mov     si,OFFSET exe19       ; VISU/C/U2E.C: city flyover
        call    partexecute
        mov     si,OFFSET exe2021     ; END/END.C: end logo / transition
        call    partexecute
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
