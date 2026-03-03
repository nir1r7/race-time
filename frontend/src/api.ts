import { Snapshot } from "./types";

export async function fetchLiveSnapshot(): Promise<Snapshot | null> {
    const res = await fetch("/api/live/snapshot")
    
    if (!res.ok){
        return null;
    }

    const data: Snapshot = await res.json();
    return data;
}