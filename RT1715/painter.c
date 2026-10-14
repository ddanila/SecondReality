/* Global face ordering: shared scratch buffers retain the 16-bit memory budget.
 * Object-centre sorting cannot resolve overlapping case/keyboard/drive faces.
 */
#include <stdlib.h>
#include <string.h>
#include "CD.H"
#include "C.H"

#define MAX_FACES 4000
struct face_entry { object *owner; int offset; long depth; };
static struct face_entry far faces[MAX_FACES];
static unsigned count;
static vlist vertices[500];
static pvlist projected[500];
static nlist normals[500];

static void transform(object *o) {
    if(o->vnum>500 || o->nnum>500) exit(3);
    o->v=vertices; o->pv=projected; o->n=normals;
    calc_rotate(o->vnum,o->v,o->v0,o->r);
    calc_nrotate((o->flags&F_GOURAUD)?o->nnum:o->nnum1,o->n,o->n0,o->r);
    o->vf=calc_project(o->vnum,o->pv,o->v);
}

void rt_begin(void) { count=0; }
void rt_queue(object *o) {
    int i,j,n,offset,*face;
    vlist *v; nlist *normal;
    long facing;
    long depth,nearest=0x7fffffffL;
    if(!(o->flags&F_VISIBLE)) return;
    transform(o);
    if(o->vf) return;
    for(i=0;i<o->vnum;i++) if(o->v[i].z<nearest) nearest=o->v[i].z;
    n=o->pl[0][0]-3;
    for(i=0;i<n;i++) {
        offset=o->pl[0][i+2]; face=(int *)(o->pd+offset);
        v=&o->v[face[3]];normal=&o->n[face[2]];
        facing=(v->x/16)*normal->x+(v->y/16)*normal->y+(v->z/16)*normal->z;
        if(!(face[0]&F_2SIDE) && facing>=0) continue;
        depth=0;
        for(j=0;j<(face[0]&255);j++) depth+=o->v[face[j+3]].z;
        depth/=(face[0]&255);
        /* Key ink follows its own cap, while other objects still occlude it. */
        if(!strncmp(o->name,"\"key-",5) && face[1]==96) depth=nearest-1;
        if(count==MAX_FACES) exit(3);
        faces[count].owner=o;faces[count].offset=offset;faces[count].depth=depth;
        count++;
    }
}
static int __watcall compare(const void *a,const void *b) {
    const struct face_entry *x=a,*y=b;
    return x->depth>y->depth?-1:(x->depth<y->depth?1:0);
}
void rt_flush(void) {
    unsigned i;
    object *last=NULL,*o;
    int single[4];
    qsort(faces,count,sizeof(struct face_entry),compare);
    single[0]=4;single[3]=0;
    for(i=0;i<count;i++) {
        o=faces[i].owner;
        if(o!=last) { transform(o);last=o; }
        single[1]=o->pl[0][1];single[2]=faces[i].offset;
        draw_polylist(single,o->pd,o->v,o->pv,o->n,o->flags);
    }
}
