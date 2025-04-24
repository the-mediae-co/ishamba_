export class MessageContent {
    text: string;
    id?: number;
    message_type: string;
    message_type_display: string;
    created: Date;
    constructor(obj: any){
        this.text = obj.text;
        this.id = obj.id;
        this.message_type = obj.message_type;
        this.message_type_display = obj.message_type_display;
        this.created = obj.created;
    }
}
