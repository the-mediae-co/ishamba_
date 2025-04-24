import { Component } from '@angular/core';
import { BaseAPIService } from '../services/base-api.service';
import { Commodity, Tip, TipTranslation } from '../tip-series';

@Component({
  selector: 'app-commodities',
  templateUrl: './commodities.component.html',
  styleUrls: ['./commodities.component.css']
})
export class CommoditiesComponent {
  commodities: Commodity[] = [];
  languages: any[] = [];
  showModal: boolean = false;
  headers: string[] = [
    "delay", "text", "sender"
  ];
  selected_commodity?: Commodity;
  selected_language?: string;
  showCommoditiesDropdown: boolean = true;
  tips: Tip[] = [];
  errors: any = {};
  constructor(private api: BaseAPIService) {
    this.api.list<Commodity[]>('/api/agri/commodities/').subscribe(
      (response) => {
        this.commodities = response;
      }
    );
    this.api.list<any>('/api/sms/metadata/').subscribe(
      (response) => {
        this.languages = response['languages'];
      }
    );
  }
  openModal(){
    this.showModal = true;
  }
  closeModal(){
    this.showCommoditiesDropdown = true;
    this.selected_commodity = undefined;
    this.showModal = false;
  }
  updateTips(data: {headers: string[], content: string[][]}) {
    delete this.errors.tips;
    let tips = data.content;
    let selected_language = this.selected_language || 'eng';
    tips.forEach(
      (tip) => {
        let delay = parseInt(tip[0])
        if (isNaN(delay)){
          this.errors['tips'] = "Delay must be a valid whole number for all tips"
        }
        else {
          let tip_obj = new Tip({delay_days: delay});
          tip_obj.translations.push(
            new TipTranslation({language: selected_language, text: tip[1]})
          );
          this.tips.push(tip_obj);
        }

      }
    );
  }
  updateTipsError(error: string) {
    this.errors['tips'] = error
  }
  uploadTips() {
    if(this.selected_commodity){
      this.api.create(
        `/api/advisory/tips/`, {tips: this.tips, commodity_id: this.selected_commodity.id}
      ).subscribe(
        (tips) => {
          this.closeModal();
        }
      )
    }
  }
  openTipsModal(commodity: Commodity) {
    this.selected_commodity = commodity;
    this.showCommoditiesDropdown = false;
    this.showModal = true;
  }
  toggleTips(commodity: Commodity){
    let tips_toggle_url = commodity.tips_enabled?'enable_tips': 'disable_tips';
    this.api.post(
      `/api/agri/commodities/${commodity.id}/${tips_toggle_url}/`, {}
    )
  }
}
