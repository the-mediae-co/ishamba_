import { Component, OnInit } from '@angular/core';
import { BaseAPIService } from '../services/base-api.service';
import {ActivatedRoute, Router} from "@angular/router";
import {Customer, CustomerFetchResponse} from "./customer";

@Component({
  selector: 'app-customers',
  templateUrl: './customers.component.html',
  styleUrls: ['./customers.component.css']
})
export class CustomersComponent implements OnInit {
  customerFilters: any = {
    page: 1,
    q: ''
  }
  currentPage: number = 1;
  totalCount: number = 0;
  commodity_id?: string;
  query: string = "";
  loading: boolean = false;
  showModal: boolean = false;
  newMessageText: string = "";
  errors: any = {};
  headers: string[] = ['id']
  recipients: string[] = [];
  eta?: Date;
  ngOnInit(): void {
    this.activatedRoute.queryParams.subscribe(
      (params) => {
        if (params['page']){
          let parsedPage = parseInt(params['page']);
          if (isNaN(parsedPage)){
            this.customerFilters['page'] = 1
          } else {
            this.customerFilters['page'] = parsedPage
          }
        }
        if (params['tips_commodity']){
          this.customerFilters['tips_commodity'] = params['tips_commodity']
        }
        if (params['q']){
          this.customerFilters['q'] = params['q']
        }
        if (params['subscribed_to_tips']){
          this.customerFilters['subscribed_to_tips'] = params['subscribed_to_tips']
        }
      }
    )
  }
  constructor(private api: BaseAPIService, private activatedRoute: ActivatedRoute, private router: Router) { }

  changePage(pageNumber: number | string){
    let parsedPageNumber = Number(pageNumber);
    if (!isNaN(parsedPageNumber) && parsedPageNumber != this.currentPage){
      this.customerFilters['page'] = parsedPageNumber
    }
  }

  updateUrlParams(){

    this.router.navigate(
        [],
        {
          queryParams: this.customerFilters,
          relativeTo: this.activatedRoute,
          replaceUrl: true
        }
    );
  }
  filtersChanged(newFilters: any){
    this.customerFilters = newFilters;
    console.log(this.customerFilters)
    this.updateUrlParams()
  }
  openModal(){
    this.eta = undefined;
    this.showModal = true;
  }
  closeModal() {
    this.showModal = false
    this.recipients = [];
    this.errors = {};
    this.newMessageText = "";
  }

  updateRecipients(data: {headers: string[], content: string[][]}) {
    delete this.errors.recipients;
    this.recipients=data.content.map(row => row[0]);
  }
  updateRecipientsError(error: string) {
    this.errors['recipients'] = error
  }

  updateEta(event: any) {
    let selectedEta = new Date(event.target.value);
    if (selectedEta > new Date(Date.now())){
      delete this.errors.eta;
      this.eta = selectedEta;
    } else {
      this.errors['eta'] = "ETA must be in the future";
    }
  }
  saveMessage(){
    if(this.newMessageText && this.recipients){
      this.api.create(
        '/api/sms/outgoing_sms/',
        {text: this.newMessageText, customer_ids: this.recipients, eta: this.eta}
      ).subscribe(
        (response) => {
          this.closeModal()
        },
        (error) => {
          this.errors.recipients = error.error.errors[0]['msg']
        }
      )
    }
  }
}
