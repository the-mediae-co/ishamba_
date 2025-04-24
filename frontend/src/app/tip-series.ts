export class TipTranslation {
    id?: number;
    language: string;
    text: string;
    constructor(obj: any) {
        this.id = obj.id;
        this.language = obj.language;
        this.text = obj.text;
    }
}

export class Commodity {
    id: number;
    name: string;
    variant_of_id?: number;
    commodity_type: string;
    season_length_days?: number;
    tips_enabled: boolean;
    tips_count: number;
    call_center_tips_count: number;
    constructor(obj: any) {
        this.id = obj.id;
        this.name = obj.name;
        this.commodity_type = obj.commodity_type;
        this.season_length_days = obj.season_length_days;
        this.variant_of_id = obj.variant_of_id;
        this.tips_enabled = obj.tips_enabled;
        this.tips_count = obj.tips_count;
        this.call_center_tips_count = obj.call_center_tips_count;
    }
}

export class Tip {
    id: number;
    delay_days: number;
    delay: number;
    delay_before: boolean;
    translations: TipTranslation[];
    current_translation?: TipTranslation;
    constructor(obj: any) {
        this.id = obj?.id;
        this.delay_days = obj.delay_days;
        this.delay = this.delay_days * 3600 * 24;
        this.delay_before = obj.delay_before || false;
        this.translations = obj.translations || [];
    }

    get_translation(language: string) : TipTranslation | undefined {
      let found_translation = this.translations.find(translation => translation.language == language)
      console.log(found_translation)
      return found_translation
  }
}


export class TipSeries {
    id: number;
    name: string;
    tips: Tip[];
    commodity_id: number;
    commodity: Commodity;
    constructor(obj: any) {
        this.id = obj.id;
        this.name = obj.name;
        this.tips = obj.tips;
        this.commodity_id = obj.commodity_id;
        this.commodity = obj.commodity
    }
}


export class TipSeason {
    id: number;
    start_date: Date;
    commodity_id: number;
    customer_filters: {border3: number[]};
    constructor(obj: any) {
        this.id = obj.id;
        this.start_date = obj.start_date;
        this.commodity_id = obj.commodity_id;
        this.customer_filters = obj.customer_filters
    }
}


export class BorderLevel {
    id: number;
    level: number;
    name: string;
    country: string;
    constructor(obj: any) {
        this.id = obj.id,
        this.level = obj.level;
        this.name = obj.name;
        this.country = obj.country;
    }
}

export class Border {
    id: number;
    parent_id: number;
    level: number;
    name: string;
    country: string;
    constructor(obj: any) {
        this.id = obj.id,
        this.parent_id = obj.parent_id;
        this.level = obj.level;
        this.name = obj.name;
        this.country = obj.country;
    }
}
