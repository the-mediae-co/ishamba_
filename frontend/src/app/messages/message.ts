import { MessageContent } from "./message-content";

export class Message {
    id?: number;
    message_id: number;
    recipient_id: number;
    created: Date;
    delivery_status: string;

    constructor(obj: any){
        this.id = obj.id;
        this.message_id = obj.message_id;
        this.recipient_id = obj.recipient_id;
        this.created = obj.created;
        this.delivery_status = obj.delivery_status
    }
}


export class MessageContentResponse {
    page: number;
    size: number;
    next_page?: number;
    previous_page?: number;
    items: MessageContent[];
    total_count: number = 0;

    constructor(obj: any) {
        this.page = obj.page;
        this.size = obj.size;
        this.next_page = obj.next_page;
        this.previous_page = obj.previous_page;
        this.items = obj.items
    }
}


export class MessageResponse {
    page: number;
    size: number;
    next_page?: number;
    previous_page?: number;
    items: Message[];
    total_count: number = 0;

    constructor(obj: any) {
        this.page = obj.page;
        this.size = obj.size;
        this.next_page = obj.next_page;
        this.previous_page = obj.previous_page;
        this.items = obj.items
    }
}
