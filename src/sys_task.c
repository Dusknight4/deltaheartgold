#include "sys_task.h"

#include "global.h"

void SysTaskQueue_InitTask(SysTaskQueue *queue, SysTask *task);
void SysTaskQueue_InitStack(SysTaskQueue *queue);
SysTask *SysTaskQueue_CreateTask(SysTaskQueue *queue);
BOOL SysTaskQueue_DeleteTask(SysTaskQueue *queue, SysTask *task);
void SysTaskQueue_Init(SysTaskQueue *queue);
SysTask *SysTaskQueue_InsertTaskCore(SysTaskQueue *queue, SysTaskFunc func, void *data, u32 priority);

void SysTaskQueue_InitTask(SysTaskQueue *queue, SysTask *task) {
    task->queue = queue;
    task->prev = task->next = &queue->headSentinel;
    task->priority = 0;
    task->data = NULL;
    task->func = NULL;
}

void SysTaskQueue_InitStack(SysTaskQueue *queue) {
    for (int i = 0; i < queue->limit; ++i) {
        SysTaskQueue_InitTask(queue, &queue->taskList[i]);
        queue->taskStack[i] = &queue->taskList[i];
    }
    queue->activeCount = 0;
}

SysTask *SysTaskQueue_CreateTask(SysTaskQueue *queue) {
    if (queue->activeCount == queue->limit) {
        return NULL;
    }
    SysTask *ret = queue->taskStack[queue->activeCount];
    ++queue->activeCount;
    return ret;
}

BOOL SysTaskQueue_DeleteTask(SysTaskQueue *queue, SysTask *task) {
    if (queue->activeCount == 0) {
        return FALSE;
    }
    task->queue = queue;
    task->prev = task->next = &queue->headSentinel;
    task->priority = 0;
    task->data = NULL;
    task->func = NULL;
    --queue->activeCount;
    queue->taskStack[queue->activeCount] = task;
    return TRUE;
}

u32 SysTaskQueue_GetArenaSize(u32 num) {
    return num * (sizeof(SysTask) + sizeof(SysTask *)) + sizeof(SysTaskQueue);
}

SysTaskQueue *SysTaskQueue_PlacementNew(u32 num, void *p_mem) {
    GF_ASSERT(p_mem != NULL);

    SysTaskQueue *ret = (SysTaskQueue *)p_mem;
    SysTask **taskStack = (SysTask **)&ret[1];
    ret->taskStack = taskStack;
    SysTask *taskList = (SysTask *)&taskStack[num];
    ret->taskList = taskList;
    ret->limit = num;
    ret->activeCount = 0;
    ret->isInsertingTask = 0;
    SysTaskQueue_Init(ret);
    return ret;
}

void SysTaskQueue_Init(SysTaskQueue *queue) {
    SysTaskQueue_InitStack(queue);
    queue->headSentinel.queue = queue;
    queue->headSentinel.prev = queue->headSentinel.next = &queue->headSentinel;
    queue->headSentinel.priority = 0;
    queue->headSentinel.data = NULL;
    queue->headSentinel.func = NULL;
    queue->runningTask = queue->headSentinel.next;
}

void SysTaskQueue_RunTasks(SysTaskQueue *queue) {
    if (!queue->isInsertingTask) {
        queue->runningTask = queue->headSentinel.next;
        while (queue->runningTask != &queue->headSentinel) {
            queue->nextTask = queue->runningTask->next;
            if (!queue->runningTask->runNow) {
                if (queue->runningTask->func != NULL) {
                    queue->runningTask->func(queue->runningTask, queue->runningTask->data);
                }
            } else {
                queue->runningTask->runNow = FALSE;
            }
            queue->runningTask = queue->nextTask;
        }
        queue->runningTask->func = NULL;
    }
}

SysTask *SysTaskQueue_InsertTask(SysTaskQueue *queue, SysTaskFunc func, void *data, u32 priority) {
    queue->isInsertingTask = TRUE;
    SysTask *ret = SysTaskQueue_InsertTaskCore(queue, func, data, priority);
    queue->isInsertingTask = FALSE;
    return ret;
}

SysTask *SysTaskQueue_InsertTaskCore(SysTaskQueue *queue, SysTaskFunc func, void *data, u32 priority) {
    SysTask *ret = SysTaskQueue_CreateTask(queue);
    SysTask *tail;
    if (ret == NULL) {
        return NULL;
    }
    ret->priority = priority;
    ret->data = data;
    ret->func = func;

    if (queue->runningTask->func != NULL) {
        if (queue->runningTask->priority <= priority) {
            ret->runNow = TRUE;
        } else {
            ret->runNow = FALSE;
        }
    } else {
        ret->runNow = FALSE;
    }
    for (tail = queue->headSentinel.next; tail != &queue->headSentinel; tail = tail->next) {
        if (tail->priority > ret->priority) {
            ret->prev = tail->prev;
            ret->next = tail;
            tail->prev->next = ret;
            tail->prev = ret;
            if (tail == queue->nextTask) {
                queue->nextTask = ret;
            }
            return ret;
        }
    }
    if (queue->nextTask == &queue->headSentinel) {
        queue->nextTask = ret;
    }
    ret->prev = queue->headSentinel.prev;
    ret->next = &queue->headSentinel;
    queue->headSentinel.prev->next = ret;
    queue->headSentinel.prev = ret;
    return ret;
}

BOOL SysTask_Unlink(SysTask *task) {
    // HARDWARE CRASH FIX (2026-09-23): task can legitimately be NULL here. This is the shared
    // low-level accessor underneath SysTask_Destroy/SysTask_GetData/SysTask_SetFunc/SysTask_GetPriority,
    // called from dozens of sites across this codebase (both decompiled C and raw, undecompiled overlay
    // assembly) - too many to individually audit for "was this SysTask ever actually created" with
    // confidence, especially the asm call sites. Two separate real-hardware "Error: Data Abort!" reports
    // this session (ADDR 0x00000010, matching the `data` field at this struct's offset 0x10 - see
    // SysTask_GetData below) both resolved to a NULL task reaching this shared plumbing from a different,
    // hard-to-pin-down caller each time (once returning from the party screen, once leaving a building).
    // Rather than keep chasing individual unguarded callers - especially in raw asm, where this project's
    // own crash-resolution notes already flag address-based caller identification as unreliable due to
    // overlapping overlay memory regions - hardening every accessor in this shared utility to tolerate
    // NULL (a no-op / safe-default return, the same convention Heap_Free and DestroySysTaskAndEnvironment
    // already follow) protects every current and future caller at once.
    if (task == NULL) {
        return FALSE;
    }

    GF_ASSERT(task->func != NULL);
    if (task->queue->nextTask == task) {
        task->queue->nextTask = task->next;
    }
    task->prev->next = task->next;
    task->next->prev = task->prev;
    return SysTaskQueue_DeleteTask(task->queue, task);
}

void SysTask_SetFunc(SysTask *task, SysTaskFunc func) {
    // HARDWARE CRASH FIX (2026-09-23): see the identical guard/comment on SysTask_Unlink above.
    if (task == NULL) {
        return;
    }
    task->func = func;
}

// HARDWARE CRASH FIX (2026-09-23) / REVERTED LATER THE SAME DAY - READ BEFORE TOUCHING THIS AGAIN:
// grepping every raw asm overlay file for "bl CreateSysTaskAndEnvironment" found 15+ more call sites
// (overlay_01_021EFB38.s, overlay_01_021F4464.s, overlay_05.s, overlay_08.s (x2), overlay_28/29/31/32/
// 33/34/41.s (x4)/70.s (x2)/overlay_80_0223A00C.s/106.s, render_window.s, unk_020163E0.s) following the
// same unguarded template as overlay_27.s (fixed properly, see SysTask_Unlink's own comment above): create
// the task, immediately call SysTask_GetData on it, then unconditionally write several fields into the
// result with no NULL check - e.g. "bl CreateSysTaskAndEnvironment / bl SysTask_GetData / add r4, r0, #0 /
// str r5, [r4, #8]".
//
// A FIRST ATTEMPT at this had SysTask_GetData(NULL) return a pointer to a fixed-size static scratch
// buffer instead of NULL, on the theory that every one of those callers' subsequent field writes would
// then land somewhere harmless. THIS WAS WRONG AND WAS REVERTED: checking the actual environment SIZE
// (the 2nd arg to each site's own CreateSysTaskAndEnvironment call, i.e. the r1 value right before it)
// found sizes from 16 bytes up to 0x2090 = 8336 bytes (overlay_08.s) and 0xBD4 = 3028 bytes (overlay_05.s)
// - several others (overlay_28/29/32/34.s) also exceed a 512-byte guess. A shared buffer sized for the
// common case silently overflows into WHATEVER STATIC DATA happens to follow it for the larger ones -
// trading a loud, localized, diagnosable crash for silent, wide-reaching memory corruption with no crash
// dump at all. This is a strictly worse failure mode, and is the likely cause of a cluster of new
// hangs/soft-locks (blank bottom-screen UI after battle, controls freezing mid-battle-transition, a
// Pokemon Center dialogue hanging) reported after that "fix" shipped - all in subsystems with no
// obvious connection to SysTasks, exactly what stray writes into unrelated globals would produce.
// SysTask_GetData(NULL) returning NULL again (reverting to the ENTRY AQ behavior) is intentional: a
// caller that dereferences a NULL environment crashes immediately and loudly, at a specific, resolvable
// PC/ADDR (see how overlay_27.s's real instance was found and fixed by that exact route) - which is
// diagnosable and fixable one call site at a time, unlike memory corruption. Do not reintroduce a
// one-size-fits-all dummy buffer here; if more of these 15+ sites are confirmed to actually crash, fix
// them individually the way overlay_27.s was fixed (a targeted NULL check + branch to that function's own
// existing epilogue), sized to that function's own real environment, not a shared guess.
void *SysTask_GetData(SysTask *task) {
    // HARDWARE CRASH FIX (2026-09-23): see the identical guard/comment on SysTask_Unlink above - this is
    // the exact function both confirmed real-hardware crashes resolved to (ADDR 0x10 = offsetof(SysTask,
    // data)).
    if (task == NULL) {
        return NULL;
    }
    return task->data;
}

u32 SysTask_GetPriority(SysTask *task) {
    // HARDWARE CRASH FIX (2026-09-23): see the identical guard/comment on SysTask_Unlink above.
    if (task == NULL) {
        return 0;
    }
    return task->priority;
}
