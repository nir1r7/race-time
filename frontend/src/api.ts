import { Snapshot } from "./types";

/*
============= Obsolete =============
Keeping around for future reference
*/

// export async function fetchLiveSnapshot(): Promise<Snapshot | null> {
//     const res = await fetch("/api/live/snapshot")
    
//     if (!res.ok){
//         return null;
//     }

//     const data: Snapshot = await res.json();
//     return data;
// }