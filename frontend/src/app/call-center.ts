export class CallCenter {
    name: string;
    call_center_id: number;
    constructor(name: string, call_center_id: number){
        this.name = name;
        this.call_center_id = call_center_id;
    }
}


export class CallCenterData {
    current_call_center?: CallCenter;
    call_centers: CallCenter[];
    tips_enabled: boolean;
    constructor(current_call_center?: CallCenter, call_centers?: CallCenter[], tips_enabled?: boolean){
        this.current_call_center = current_call_center;
        this.call_centers = call_centers || [];
        this.tips_enabled = tips_enabled || true;
    }
}
