import {Component, EventEmitter, Input, OnInit, Output} from '@angular/core';
import {BaseAPIService} from "../../services/base-api.service";

@Component({
  selector: 'app-customer-filter-panel',
  templateUrl: './customer-filter-panel.component.html',
  styleUrls: ['./customer-filter-panel.component.css']
})
export class CustomerFilterPanelComponent implements OnInit{
  @Input() commodity_id?: string;
  commodities: any[] = [];
  @Input() query: string = "";
  @Input() subscribedToTips: boolean = false;
  @Output() filterChangeEvent = new EventEmitter<any>();
  constructor(private api: BaseAPIService) {
  }
  ngOnInit() {
    this.api.list<any>('/api/agri/commodities/').subscribe(
      (response) => {
        this.commodities = response;
      }
    );
  }

  queryChanged(q: string){
    this.filtersChanged()
  }

  tipCommodityChanged(commodity_id: string){
    this.commodity_id = commodity_id
    this.filtersChanged()
  }
  toggleTipSubscription(){
    this.filtersChanged()
  }
  filtersChanged(){
    let queryParams: any = {}
    if (this.query){
      queryParams['q'] = this.query
    }
    if (this.subscribedToTips){
      queryParams['subscribed_to_tips'] = this.subscribedToTips
    }
    if (this.commodity_id){
      queryParams['tips_commodity'] = this.commodity_id
    }
    this.filterChangeEvent.emit(
      queryParams
    )
  }
}
