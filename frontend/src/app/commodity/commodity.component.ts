import {AfterViewInit, Component, OnDestroy, OnInit} from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import {Border, BorderLevel, Commodity, Tip, TipSeason, TipSeries, TipTranslation} from '../tip-series';
import { BaseAPIService } from '../services/base-api.service';
import { Customer, CustomerFetchResponse } from '../customers/customer';

@Component({
  selector: 'app-commodity',
  templateUrl: './commodity.component.html',
  styleUrls: ['./commodity.component.css']
})
export class CommodityComponent implements OnInit, OnDestroy {
  private sub: any;
  commodity?: Commodity;
  selected_language: string = 'eng';
  languages: any[] = [];
  tip_seasons: TipSeason[] = [];
  selected_seasons: TipSeason[] = [];
  customers: Customer[] = [];
  openTab = 1;
  showModal = false;
  showCustomersModal = false;
  showTipsModal = false;
  start_date?: Date;
  borderFilters: number[] = [];
  borderLevels: BorderLevel[] = [];
  borderChoices: any = {};
  errors: any = {};
  headers: string[] = ['border1', 'border2', 'border3', 'planting_date'];
  tipsHeaders: string[] = [
    "delay", "text", "sender"
  ];
  seasonsData: string[][] = [];
  customersData: string[] = [];
  errorData: string[][] = [];
  tips: Tip[] = [];
  newTips: Tip[] = [];
  currentPage: number = 1;
  query: string = "";
  selectedTip?: Tip;
  customerFilters: any = {}
  constructor(private route: ActivatedRoute, private api: BaseAPIService){}
  ngOnInit() {
    this.sub = this.route.params.subscribe(params => {
      this.api.retrieve<Commodity>('/api/agri/commodities/', params['commodity_id']).subscribe(
        (response) => {
          this.commodity = response;
          this.customerFilters = {...this.customerFilters, tips_commodity: this.commodity.id}
          this.api.list<Tip[]>(`/api/advisory/tips/?commodity_id=${this.commodity.id}`).subscribe(
            (response) => {
              response.forEach(tip => tip.current_translation = tip.translations.find(
                (translation) => {
                  return translation.language === this.selected_language;
                })
              )
              this.tips = response;
            }
          );
          this.api.list<TipSeason[]>(`/api/advisory/tip_seasons/?commodity_id=${this.commodity.id}`).subscribe(
              response => this.tip_seasons = response
            );
          }
      );
      this.api.list<any>('/api/sms/metadata/').subscribe(
        (response) => {
          this.languages = response['languages'];
        }
      );

      this.api.list<BorderLevel[]>('/api/world/border_levels/?country=kenya').subscribe(
        response => this.borderLevels = response.slice(1)
      );
    });
     this.route.queryParams.subscribe(params => this.openTab = params['view'] == 'seasons'? 2: 1)
  }
  ngOnDestroy() {
    this.sub.unsubscribe();
  }

  toggleTabs($tabNumber: number){
    this.openTab = $tabNumber;
  }
  toggleModal(){
    this.showModal = !this.showModal;
  }

  updateSeasons(data: {headers: string[], content: string[][]}) {
    delete this.errors.seasons;
    this.seasonsData = data.content;
  }
  updateSeasonsError(error: string) {
    this.errors['seasons'] = error
  }
  openCustomersModal() {
    this.showCustomersModal = true;
  }
  closeCustomersModal() {
    this.showCustomersModal = false;
    this.customersData = []
  }
  updateCustomers(data: {headers: string[], content: string[][]}) {
    delete this.errors.customers;
    this.customersData = data.content.map(item => item[0]);
  }
  updateCustomersError(error: string) {
    this.errors['customers'] = error
  }

  saveTipSeason() {
    if (this.commodity){
      let tip_season = new TipSeason({start_date: this.start_date, series_id: this.commodity.id})
      this.api.create<TipSeason>(`/api/advisory/tip_seasons/${this.commodity.id}/`, tip_season).subscribe(
        (new_tip_season) => {
          this.tip_seasons.push(new_tip_season);
          this.toggleModal();
        }
      )
    }

  }
  saveTipSeasons() {
    if (this.commodity){
      this.api.post<string[][]>(`/api/advisory/tip_seasons/${this.commodity.id}/`, this.seasonsData).subscribe(
        (response) => {
          this.errorData = response;
          if (this.commodity){
            this.api.list<TipSeason[]>(`/api/advisory/tip_seasons/${this.commodity.id}/`).subscribe(
              response => this.tip_seasons = response
            );
          }

          this.toggleModal();
          if (response.length > 0){
            let csvContent = "data:text/csv;charset=utf-8," + response.map(e => e.join(",")).join("\n");
            var encodedUri = encodeURI(csvContent);
            window.location.href = encodedUri;
          }
        }
      )
    }

  }
  saveCustomers() {
    if (this.commodity){
      this.api.post(`/api/crm/commodities/${this.commodity.id}/`, this.customersData).subscribe(
        (response) => {
          this.customerFilters = {...this.customerFilters}
        }
      )
    }
    this.closeCustomersModal()
  }
  onKeyUp($event: any, level: number) {
    let url = `/api/world/borders/?country=kenya&level=${level}&search=${$event.target.value}`;
    if (level > 1 && this.borderFilters[level-1]){
      url += `&parent=${this.borderFilters[level-1]}`
    }
    this.api.list<Border[]>(url).subscribe(
      response => this.borderChoices[level] = response
    )
  }

  filterCustomers(value: any){
    if(value != this.query){
      this.query = value;
      this.currentPage = 1;
      this.customerFilters = {...this.customerFilters, page: 1, q: value}
      console.log(this.customerFilters)
    }
  }
  selectionChanged(event: any, season: TipSeason){
    if (event.target.checked){
      this.selected_seasons.push(season);
    } else {
      let seasonIdx = this.selected_seasons.indexOf(season)
      if (seasonIdx > -1) {
        this.selected_seasons.splice(seasonIdx, 1)
      }
    }
  }
  openTipUpdateModal(tip: Tip) {
    this.selectedTip = tip;
  }
  closeTipUpdateModal() {
    this.selectedTip = undefined;
  }
  saveUpdatedTip() {
    if (this.selectedTip){
      this.api.patch('/api/advisory/tips/', this.selectedTip.id.toString(), this.selectedTip).subscribe(
        response => console.log(response)
      )
    }
    this.selectedTip = undefined
  }
  toggleTips(){
    if (this.commodity){
      let tips_toggle_url = this.commodity?.tips_enabled?'enable_tips': 'disable_tips';
      this.api.post(
        `/api/agri/commodities/${this.commodity.id}/${tips_toggle_url}/`, {}
      ).subscribe(response=>console.log(response, tips_toggle_url))
    }

  }
  languageChanged() {
    this.tips.forEach(tip => tip.current_translation = tip.translations.find(
        (translation) => {
          return translation.language === this.selected_language;
        })
      )
  }
  updateTipsError(error: string) {
    this.errors['tips'] = error
  }
  uploadTips() {
    if(this.commodity){
      this.api.create(
        `/api/advisory/tips/`, {tips: this.newTips, commodity_id: this.commodity.id}
      ).subscribe(
        (tips) => {
          this.closeTipsModal();
          if (this.commodity){
            this.api.list<Tip[]>(`/api/advisory/tips/?commodity_id=${this.commodity.id}`).subscribe(
            (response) => {
              response.forEach(tip => tip.current_translation = tip.translations.find(
                (translation) => {
                  return translation.language === this.selected_language;
                })
              )
              this.tips = response;
            }
          );
          }

        }
      )
    }
  }
  openTipsModal(value: any) {
    this.showTipsModal = true;
  }

  closeTipsModal(){
    this.showTipsModal = false;
  }
  updateNewTips(data: {headers: string[], content: string[][]}) {
    delete this.errors.tips;
    let tips = data.content;
    tips.forEach(
      (tip) => {
        let delay = parseInt(tip[0])
        if (isNaN(delay)){
          this.errors['tips'] = "Delay must be a valid whole number for all tips"
        }
        else {
          let tip_obj = new Tip({delay_days: delay});
          tip_obj.translations.push(
            new TipTranslation({language: this.selected_language, text: tip[1]})
          );
          this.newTips.push(tip_obj);
        }

      }
    );
  }
}
