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
    int i,j,n,offset,*face,clip,key,coarse;
    vlist *v; nlist *normal;
    long facing;
    long depth,nearest=0x7fffffffL;
    if(!(o->flags&F_VISIBLE)) return;
    key=!strncmp(o->name,"\"key-",5);
    coarse=0;
    if(key) {
        /* The first six faces use exactly eight envelope vertices. Decide
         * LOD before transforming hundreds of tiny legend vertices. */
        o->v=vertices;o->pv=projected;o->n=normals;
        calc_rotate(8,vertices,o->v0,o->r);
        for(i=0;i<8;i++) if(vertices[i].z<nearest) nearest=vertices[i].z;
        coarse=nearest>240L*64L;
        if(coarse) {
            calc_nrotate(6,normals,o->n0,o->r);
            o->vf=calc_project(8,projected,vertices);
        }
    }
    if(!coarse) transform(o);
    if(o->vf) return;
    n=o->pl[0][0]-3;
    for(i=key && !coarse ? 6 : 0;i<(coarse ? 6 : n);i++) {
        offset=o->pl[0][i+2]; face=(int *)(o->pd+offset);
        clip=31;
        for(j=0;j<(face[0]&255);j++) clip&=o->pv[face[j+3]].vf;
        if(clip) continue;
        v=&o->v[face[3]];normal=&o->n[face[2]];
        facing=(v->x/16)*normal->x+(v->y/16)*normal->y+(v->z/16)*normal->z;
        if(!(face[0]&F_2SIDE) && facing>=0) continue;
        depth=0;
        for(j=0;j<(face[0]&255);j++) depth+=o->v[face[j+3]].z;
        depth/=(face[0]&255);
        /* Key ink follows its own cap, while other objects still occlude it. */
        if(key && face[1]==96) depth=nearest-1;
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
    object *o,*cached=NULL;
    int j,index,first,last,*face;
    int single[4];
    qsort(faces,count,sizeof(struct face_entry),compare);
    single[0]=4;single[3]=0;
    for(i=0;i<count;i++) {
        o=faces[i].owner;
        face=(int *)(o->pd+faces[i].offset);
        /* Sorting interleaves objects. Transform only this face, not every
         * vertex in its owner again. Keep full normals for Gouraud objects. */
        if(o==cached) { /* Consecutive faces reuse a full transform. */ }
        else if((o->flags&F_GOURAUD) ||
                (i+5<count && faces[i+1].owner==o && faces[i+2].owner==o && faces[i+5].owner==o)) {
            transform(o);cached=o;
        } else {
            cached=NULL;
            o->v=vertices;o->pv=projected;o->n=normals;
            first=last=face[3];
            for(j=1;j<(face[0]&255);j++) {
                index=face[j+3];
                if(index<first) first=index;
                if(index>last) last=index;
            }
            calc_rotate(last-first+1,vertices+first,o->v0+first,o->r);
            calc_project(last-first+1,projected+first,vertices+first);
            index=face[2];
            calc_nrotate(1,normals+index,o->n0+index,o->r);
        }
        single[1]=o->pl[0][1];single[2]=faces[i].offset;
        draw_polylist(single,o->pd,o->v,o->pv,o->n,o->flags);
    }
}
