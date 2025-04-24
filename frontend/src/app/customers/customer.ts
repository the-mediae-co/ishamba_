export class Customer {
    id: number;
    name: string;
    commodities: number[];
    tips_commodities: number[];
    categories: number[];
    subscription_type: number;
    border0_id: number;
    border1_id: number;
    border2_id: number;
    border3_id: number;

    constructor(obj: any) {
        this.id = obj.id;
        this.name = obj.name;
        this.commodities = obj.commodities;
        this.tips_commodities = obj.tips_commodities;
        this.categories = obj.categories;
        this.subscription_type = obj.subscription_type;
        this.border0_id = obj.border0_id;
        this.border1_id= obj.border0_id;
        this.border2_id= obj.border0_id;
        this.border3_id= obj.border0_id;
    }
}

export class CustomerFetchResponse {
    page: number;
    size: number;
    next_page?: number;
    previous_page?: number;
    items: Customer[];
    total_count: number = 0;

    constructor(obj: any) {
        this.page = obj.page;
        this.size = obj.size;
        this.next_page = obj.next_page;
        this.previous_page = obj.previous_page;
        this.items = obj.items
    }
}
