#ifndef RT_BAKED_H
#define RT_BAKED_H
extern int rt_use_masks,rt_use_faces,rt_use_projection;
extern int rt_baked_active;
extern unsigned long rt_baked_hits,rt_baked_reads,rt_baked_memory;
void rt_baked_close(void);
void rt_baked_init(unsigned long hash,unsigned objects);
int rt_baked_prepare(unsigned frame);
int rt_baked_face(unsigned object,unsigned face);
void rt_baked_draw(void);
void rt_baked_finish(void);
void rt_baked_forget(void);
#endif
