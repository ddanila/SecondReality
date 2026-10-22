#!/usr/bin/env python3
"""Build isolated full-demo launchers and record original scene cue boundaries."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
from build import HERE, ROOT, masm_source, tool

TRACE = r'''
full_ticks dd 0
full_module dw 0
full_count dw 0
full_records db 4096 dup(0)
full_logname db 'SCENES.BIN',0
full_record PROC NEAR
    pushf
    pushad
    push ds
    push es
    mov dx,cs
    mov ds,dx
    mov es,dx
    mov di,OFFSET full_records
    add di,full_count
    cmp full_count,4032
    jae full_record_done
    mov [di+16],ax
    mov ax,full_module
    mov [di+18],ax
    mov eax,full_ticks
    mov [di+24],eax
    push es
    mov es,stmikseg
    mov ax,es:_np_ord
    mov [di+20],ax
    mov ax,es:_np_row
    mov [di+22],ax
    pop es
    mov cx,13
full_copy_name:
    lodsb
    stosb
    or al,al
    jz full_copy_done
    loop full_copy_name
full_copy_done:
    add full_count,32
full_record_done:
    pop es
    pop ds
    popad
    popf
    ret
full_record ENDP
full_dump PROC NEAR
    pusha
    push ds
    mov ax,cs
    mov ds,ax
    mov dx,OFFSET full_logname
    xor cx,cx
    mov ah,3ch
    int 21h
    jc full_dump_done
    mov bx,ax
    mov dx,OFFSET full_records
    mov cx,full_count
    mov ah,40h
    int 21h
    mov ah,3eh
    int 21h
full_dump_done:
    pop ds
    popa
    ret
full_dump ENDP
'''


def launcher(stop_after=None, smoke_scene=None, robotron=False):
    code = masm_source(robotron,robotron)
    # Keep unattended setup/unpacked file IO, restore the original full sequence.
    start = code.index('IFDEF RT1715\n', code.index('local_global_partsagain:'))
    middle = code.index('\nELSE\n\tmov\tcs:notextmode,1', start)
    end = code.index('\nENDIF\nlocal_global_partsdone:', middle)
    code = code[:start] + code[middle+6:end] + "\n" + code[end+7:]
    code = code.replace('push    18 ; city music entry (decimal order index)', 'push    0 ; original full-demo entry')
    code = code.replace('inc\tcs:copperframecount', 'inc cs:full_ticks\n\tinc\tcs:copperframecount')
    code = code.replace('restartmus PROC NEAR', 'restartmus PROC NEAR\n        mov cs:full_module,ax')
    code = code.replace('partexecute PROC NEAR', TRACE + '\npartexecute PROC NEAR\n        xor ax,ax\n        call full_record\n        push si')
    code = code.replace('partexecute ENDP', 'partexecute ENDP')
    # Log after restoring the copper callbacks, before returning to the sequence.
    a = code.index('partexecute PROC NEAR'); b = code.index('partexecute ENDP', a)
    section = code[a:b].replace('        ret', '        pop si\n        mov ax,1\n        call full_record\n        ret')
    code = code[:a] + section + code[b:]
    code = code.replace('local_global_partsdone:', 'local_global_partsdone:\n        call full_dump\n')
    if robotron:
        # Removing the released lens EXE's decompressor advances its fixed
        # frame choreography by 178 retraces at the reference 300k profile.
        # Keep the preceding water image visible for that original load time.
        code=code.replace('        push si\n', '''        push si
        cmp si,OFFSET exe1112
        jne full_lens_loaded
        mov edi,cs:full_ticks
        add edi,178
full_lens_load_time:
        push edi
        mov bx,1
        int 0fch
        pop edi
        cmp cs:full_ticks,edi
        jb full_lens_load_time
full_lens_loaded:
''',1)
        marker='        mov     si,OFFSET exe19\n        call    partexecute'
        replacement="""        mov di,210
full_wait_flight_music:
        mov bx,1
        int 0fch
        mov bx,6
        int 0fch
        cmp cx,18
        je full_start_flight
        dec di
        jnz full_wait_flight_music
        jmp full_pm_failed
full_start_flight:
        mov si,OFFSET exe19
        xor ax,ax
        call full_record
        call rt_exec32
        jc full_pm_failed
        mov ah,4dh
        int 21h
        or al,al
        jnz full_pm_failed
        mov si,OFFSET exe19
        mov ax,1
        call full_record
        jmp full_pm_done
full_pm_failed:
        mov cs:errorcode,8
        jmp local_global_partsdone
full_pm_done:
"""
        if marker not in code:raise ValueError('Flyover integration anchor missing')
        code=code.replace(marker,replacement,1)
        # The reviewed renderer already includes the overview/title interval.
        code=code.replace('        mov     si,OFFSET exe2021\n        call    partexecute','',1)
    if stop_after:
        labels={"opening":"exe1", "space":"exe3a", "title":"exe3", "keycap":"exe4", "tunnel":"exe5", "monster":"exe7", "water":"exe9", "lens":"exe1112", "tape":"exe16", "unicorn":"exe18"}
        label=labels[stop_after]
        marker="mov     si,OFFSET "+label+"\n        call    partexecute"
        if marker not in code: raise ValueError("Scene stop anchor missing")
        code=code.replace(marker,marker+"\n        jmp local_global_partsdone",1)
    if smoke_scene:
        module,order,label={'tunnel':(1,13,'exe5'),'title':(0,13,'exe3'),'keycap':(1,0,'exe4'),'lens':(1,45,'exe1112'),'unicorn':(1,96,'exe18'),'interference':(1,18,'exe6'),'space':(0,10,'exe2'),'plasma':(1,60,'exe1314'),'dots':(1,75,'exe15'),'terrain':(1,92,'exe17'),'water':(1,42,'exe9'),'tape':(1,87,'exe16')}[smoke_scene]
        row={'tunnel':49,'plasma':45,'dots':60,'terrain':0,'lens':58,'unicorn':57,'title':21,'water':1}.get(smoke_scene,0)
        a=code.index('local_global_partsagain:');b=code.index('local_global_partsdone:',a)
        code=code[:a]+f"""local_global_partsagain:
        mov ax,13h
        int 10h
        call inittwk
        mov ax,{module}
        mov bx,{order}
        mov cx,48700
        call restartmus
        mov di,1400
full_smoke_music_wait:
        mov bx,1
        int 0fch
        mov bx,6
        int 0fch
        cmp cx,{order}
        ja full_smoke_music_ready
        jb full_smoke_music_next
        cmp bx,{row}
        jae full_smoke_music_ready
full_smoke_music_next:
        dec di
        jnz full_smoke_music_wait
        mov cs:errorcode,8
        jmp local_global_partsdone
full_smoke_music_ready:
        mov si,OFFSET {label}
        call partexecute
        jmp local_global_partsdone
"""+code[b:]
    return code


def build(output, stop_after=None, smoke_scene=None, robotron=False):
    output = Path(output).resolve(); dos = output/'dos'
    reviewed=HERE/'build/dos'
    if dos==reviewed or reviewed in dos.parents:
        raise ValueError('The reviewed short build must remain isolated')
    dos.mkdir(parents=True, exist_ok=True)
    for p in (ROOT/'MAIN/DATA').iterdir():
        if p.is_file(): shutil.copyfile(p, dos/p.name)
    (output/'FULL.ASM').write_text(launcher(stop_after, smoke_scene, robotron), encoding='cp437')
    shutil.copyfile(ROOT/'MAIN/STMIK.300', output/'STMIK.OBJ')
    subprocess.run([tool('jwasm'),'-q','-Cp','-omf','-FoFULL.OBJ','FULL.ASM'],cwd=output,check=True)
    subprocess.run([tool('wlink'),'format','dos','option','quiet','option','map=FULL.MAP','name','dos/FULL.EXE','file','FULL.OBJ','file','STMIK.OBJ'],cwd=output,check=True)
    (output/'runtime.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dos.iterdir()) if p.is_file()},indent=2)+'\n')
    return dos


def read_trace(path):
    data=Path(path).read_bytes()
    if len(data)%32: raise ValueError('Truncated scene trace')
    entries=[]
    for at in range(0,len(data),32):
        name=data[at:at+16].split(b'\0')[0].decode('ascii')
        phase,module,order,row,ticks=struct.unpack_from('<4HI',data,at+16)
        if phase not in (0,1) or module not in (0,1) or row>63:
            raise ValueError('Invalid scene trace record')
        entries.append(dict(executable=name,phase='entry' if phase==0 else 'exit',module=module,order=order,row=row,retrace=ticks))
    return entries

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=HERE/'build/full-reference')
    p.add_argument('--trace',type=Path)
    p.add_argument('--stop-after',choices=('opening','space','title','keycap','tunnel','monster','water','lens','tape','unicorn'))
    p.add_argument('--smoke-scene',choices=('tunnel','title','keycap','lens','unicorn','interference','space','plasma','dots','terrain','water','tape'),help='Visual smoke test only; not a timing reference')
    p.add_argument('--robotron',action='store_true',help='Use DOS EXEC and service 11 for the reviewed protected renderer')
    a=p.parse_args()
    if a.trace: print(json.dumps(read_trace(a.trace),indent=2))
    else: print(build(a.output,a.stop_after,a.smoke_scene,a.robotron))
