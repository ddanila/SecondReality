; DOS EXEC is required for a DOS extender: it needs the child's actual path in
; its environment. The original hand-made PSP inherits the launcher's path.
rt_exec_block dw 0
              dw OFFSET rt_exec_tail,0
              dw 5ch,0,6ch,0
rt_exec_tail db 0,13
rt_exec_ss dw 0
rt_exec_sp dw 0
rt_exec32 PROC NEAR
        mov ax,cs
        mov ds,ax
        mov es,ax
        mov cs:rt_exec_block[4],ax
        mov ah,51h
        int 21h
        mov cs:rt_exec_block[8],bx
        mov cs:rt_exec_block[12],bx
        mov cs:rt_exec_ss,ss
        mov cs:rt_exec_sp,sp
        mov dx,OFFSET exe19
        mov bx,OFFSET rt_exec_block
        mov ax,4b00h
        int 21h
        cli
        mov ss,cs:rt_exec_ss
        mov sp,cs:rt_exec_sp
        sti
        ret
rt_exec32 ENDP
