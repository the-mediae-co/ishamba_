import { Component, OnInit } from '@angular/core';
import { MessageContentResponse} from './message';
import { BaseAPIService } from '../services/base-api.service';
import { MessageContent } from './message-content';
import {ActivatedRoute, Router} from "@angular/router";

@Component({
  selector: 'app-messages',
  templateUrl: './messages.component.html',
  styleUrls: ['./messages.component.css']
})
export class MessagesComponent implements OnInit {
  messages: Array<MessageContent> = []
  currentPage: number = 1;
  pageSize: number = 20;
  totalCount: number = 0;
  messageType?: string;
  messageTypeChoices: any[] = [];
  query: string = "";
  loading: boolean = false;
  dataLoading: boolean = false;
  showModal: boolean = false;
  newMessageText: string = "";
  errors: any = {};
  headers: string[] = ['phone_number']
  recipients: string[] = [];
  numbers: string[] = [];
  eta?: Date;
  pageNumberArray: any[] = [];
  ngOnInit(): void {
    this.activatedRoute.queryParams.subscribe(
      (params) => {
        if (params['page']){
          let parsedPage = parseInt(params['page']);
          if (isNaN(parsedPage)){
            this.currentPage = 1
          } else {
            this.currentPage = parsedPage
          }
        }
        if (params['message_type']){
          this.messageType = params['message_type']
        }
        if (params['q']){
          this.query = params['q']
        }
      }
    )
    this.api.list<any>('/api/sms/metadata/').subscribe(
      (response) => {
        this.messageTypeChoices = response['message_types'];
      }
    );
    this.fetchData();
  }
  constructor(private api: BaseAPIService, private activatedRoute: ActivatedRoute, private router: Router) { }
  fetchData(){
    setTimeout(() => this.loading = this.dataLoading, 1000)
    this.dataLoading = true;
    let queryParams: any = {page: this.currentPage, size: this.pageSize}
    if (this.messageType) {
      queryParams.message_type = this.messageType
    }
    if (this.query) {
      queryParams.q = this.query
    }
    this.api.list<MessageContentResponse>('/api/sms/outgoing_sms/', queryParams).subscribe(
      (response) => {
        this.messages = response.items;
        this.totalCount = response.total_count;
        this.dataLoading = false;
        this.loading = false;

        this.updateUrlParams();
      }
    )
  }

  changePage(pageNumber: number | string){
    let parsedPageNumber = Number(pageNumber);
    if (!isNaN(parsedPageNumber) && parsedPageNumber != this.currentPage){
      this.currentPage = parsedPageNumber
      this.fetchData()
    }
  }
  filterSelectedOption(value: any){
    this.messageType = value;
    this.currentPage = 1;
    this.fetchData();
  }
  updateUrlParams(){
    let queryParams: any = {};
      if (this.query) {
        queryParams['q'] = this.query
      }
      if (this.messageType) {
        queryParams['message_type'] = this.messageType
      }
      if (this.currentPage > 1) {
        queryParams['page'] = this.currentPage
      }
      this.router.navigate(
          [],
          {
            queryParams: queryParams,
            relativeTo: this.activatedRoute,
            replaceUrl: true
          }
      );
  }
  filterData(value: any){
    if(value != this.query){
      this.query = value;
      this.currentPage = 1;
      this.fetchData();
    }
  }
  openModal(){
    this.eta = undefined;
    this.showModal = true;
  }
  closeModal() {
    this.showModal = false
    this.recipients = [];
    this.numbers = [];
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
    if(this.newMessageText && (this.recipients || this.numbers)){
      this.api.create(
        '/api/sms/outgoing_sms/',
        {text: this.newMessageText, customer_ids: this.recipients, phone_numbers: this.numbers, eta: this.eta}
      ).subscribe(
        (response) => {
          this.fetchData();
          this.closeModal()
        },
        (error) => {
          this.errors.recipients = error.error.errors[0]['msg']
        }
      )
    }
  }
}
