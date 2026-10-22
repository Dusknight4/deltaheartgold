#include "systask_environment.h"

#include "global.h"

#include "sys_task.h"

SysTask *CreateSysTaskAndEnvironment(SysTaskFunc function, u32 environmentSize, u32 priority, enum HeapID heapID) {
    void *environment;

    if (environmentSize != 0) {
        environment = Heap_Alloc(heapID, environmentSize);
        if (environment == NULL) {
            return NULL;
        }
        memset(environment, 0, environmentSize);
    } else {
        environment = NULL;
    }

    return SysTask_CreateOnMainQueue(function, environment, priority);
}

void DestroySysTaskAndEnvironment(SysTask *task) {
    // HARDWARE CRASH FIX (2026-09-23): task can legitimately be NULL here - CreateSysTaskAndEnvironment
    // (above) itself returns NULL on allocation failure, and at least one caller (naming_screen.c's
    // NamingScreenAppData->tasks[0..6] cleanup loop) unconditionally destroys every array slot regardless
    // of whether each one was ever successfully created. Without this guard, both SysTask_GetData(NULL)
    // (crashes reading task->data, struct offset 0x10) and SysTask_Destroy(NULL) -> SysTask_Unlink(NULL)
    // (crashes reading task->func, offset 0x14) are unconditional NULL dereferences - this exactly matches
    // a real "Error: Data Abort!" report (PC resolved to SysTask_GetData's first instruction, ADDR = 0x10)
    // reported after closing a menu / returning to the overworld from the party screen. Making this
    // function tolerate NULL (a no-op, the same convention Heap_Free and most other Destroy-style
    // functions in this codebase already follow) is the correct, general fix - it protects every current
    // and future caller of this shared utility, not just the one confirmed trigger.
    if (task == NULL) {
        return;
    }

    void *environment = SysTask_GetData(task);
    if (environment != NULL) {
        Heap_Free(environment);
    }

    SysTask_Destroy(task);
}
