import {Component, EventEmitter, Input, OnInit, Output, SimpleChanges} from '@angular/core';
import {Customer, CustomerFetchResponse} from "../customer";
import {BaseAPIService} from "../../services/base-api.service";

@Component({
  selector: 'app-customer-table',
  templateUrl: './customer-table.component.html',
  styleUrls: ['./customer-table.component.css']
})
export class CustomerTableComponent implements OnInit{
  customers: Array<Customer> = []
  currentPage: number = 1;
  totalCount: number = 0;
  commodity_id?: string;
  commodities: any[] = [];
  query: string = "";
  loading: boolean = false;
  dataLoading: boolean = false;
  showModal: boolean = false;
  errors: any = {};
  headers: string[] = ['id']
  recipients: string[] = [];
  eta?: Date;
  @Input() customerFilters: any = {};
  @Output() totalCountChangeEvent = new EventEmitter<number>();
  constructor(private api: BaseAPIService) { }

  ngOnInit() {
    this.fetchData()
  }

  fetchData(){
    setTimeout(() => this.loading = this.dataLoading, 1000)
    this.dataLoading = true;

    this.api.list<CustomerFetchResponse>('/api/crm/customers/', this.customerFilters).subscribe(
      (response) => {
        this.customers = response.items;
        if(this.totalCount != response.total_count){
          this.totalCount = response.total_count;
          this.totalCountChangeEvent.emit(this.totalCount)
        }
        this.dataLoading = false;
        this.loading = false;
      }
    )
  }
  ngOnChanges(changes: SimpleChanges) {
    this.fetchData()
  }
}
