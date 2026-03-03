
export type DriverPosition = {
    driver_number: number;
    driver_code: string;
    x_norm: number;
    y_norm: number;
}

export type LeaderBoardEntry = {
    driver_code: string;
    team: string;
    position: number;
    gap_to_leader: number;
    tire_compound: string;
}

export type SessionInfo = {
    name: string;
    circuit: string;
}

export type Snapshot = {
    timestamp: string;
    positions: DriverPosition[];
    leaderboard: LeaderBoardEntry[];
    session: SessionInfo | null;
}