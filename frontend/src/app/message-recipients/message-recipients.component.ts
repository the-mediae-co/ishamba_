import { Component, OnDestroy, OnInit } from '@angular/core';
import { Message, MessageResponse } from '../messages/message';
import { BaseAPIService } from '../services/base-api.service';
import { ActivatedRoute } from '@angular/router';
import { MessageContent } from '../messages/message-content';

@Component({
  selector: 'app-message-recipients',
  templateUrl: './message-recipients.component.html',
  styleUrls: ['./message-recipients.component.css']
})
export class MessageRecipientsComponent implements OnInit, OnDestroy {
  messages: Array<Message> = []
  message?: MessageContent;
  currentPage: number = 1;
  totalPages: number = 0;
  nextPage?: number;
  previousPage?: number;
  pageSize: number = 20;
  totalCount: number = 0;
  private sub: any;
  loading: boolean = false;
  dataLoading: boolean = false;
  messageStatusChoices = [
    {label: 'Draft', value: 'draft'},
    {label: 'Success', value: 'success'},
    {label: 'Failed', value: 'failed'},
  ]

  filterBy: string[] = ['PC','Laptop','Tablet','Smartphone','Smartwatch','Headphone','Speaker','TV','Tracker','Charger','Adapter','Cable']

  columns: string[] = ['id','name', 'category', 'brand', 'description', 'price']

  constructor(private api: BaseAPIService, private route: ActivatedRoute) { }

  ngOnInit(): void {
    this.sub = this.route.params.subscribe(params => {
      this.api.retrieve<MessageContent>('/api/sms/outgoing_sms/', params['message_id']).subscribe(
        (response) => {
          this.message = response;
          this.fetchData()
          this.pageNumbers()
        }
      )
    });
  }

  ngOnDestroy(): void {
    this.sub.unsubscribe()
  }

  fetchData(){
    this.dataLoading = true;
    setTimeout(() => this.loading = this.dataLoading, 1000)
    let queryParams: any = {page: this.currentPage, size: this.pageSize};
    if (this.message){
      queryParams['message_id'] = this.message.id
    }
    this.api.list<MessageResponse>('/api/sms/sms_recipients/', queryParams).subscribe(
      (response) => {
        this.messages = response.items;
        this.nextPage = response.next_page;
        this.previousPage = response.previous_page;
        this.totalCount = response.total_count;
        this.dataLoading = this.loading = false;
      }
    )
  }

  pageNumbers(){
    this.totalPages = Math.ceil(this.totalCount / this.pageSize);
    let left = this.currentPage - 2;
    let right = this.currentPage + 3;
    var l;
    let pagesRange = [];
    let pageNumArray = [];
    for (let i = 1; i <= this.totalPages; i++) {
      if (i == 1 || i == this.totalPages || i >= left && i < right) {
        pagesRange.push(i);
      }
    }
    for (let i of pagesRange) {
      if (l) {
          if (i - l === 2) {
            pageNumArray.push(l + 1);
          } else if (i - l !== 1) {
            pageNumArray.push('...');
          }
      }
      pageNumArray.push(i);
      l = i;
    }
    return pageNumArray
  }

  changePage(pageNumber: number | string){
    let parsedPageNumber = Number(pageNumber);
    if (!isNaN(parsedPageNumber) && parsedPageNumber != this.currentPage){
      this.currentPage = parsedPageNumber
      this.fetchData()
    }
  }
  fetchPreviousPage(){
    if (this.previousPage) {
      this.currentPage = this.previousPage;
      this.fetchData()
    }
  }

  fetchNextPage(){
    if (this.nextPage) {
      this.currentPage = this.nextPage;
      this.fetchData()
    }
  }
  filterSelectedOption(value: any){
    console.log(value)
  }
  filterData(value: any){
    console.log(value)
  }
}
