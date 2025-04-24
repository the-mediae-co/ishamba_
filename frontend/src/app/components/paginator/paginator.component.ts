import {Component, EventEmitter, Input, OnInit, Output, SimpleChanges} from '@angular/core';

@Component({
  selector: 'app-paginator',
  templateUrl: './paginator.component.html',
  styleUrls: ['./paginator.component.css']
})
export class PaginatorComponent implements OnInit{
  @Input() currentPage: number = 1;
  @Input() totalCount: number = 0;
  @Input() pageSize: number = 20;
  @Output() pageChangeEvent = new EventEmitter<number>();
  totalPages: number = 0;
  pageNumberArray: (string | number)[] = []

  ngOnInit() {
    this.pageNumbers()
  }

  pageNumbers(){
    this.totalPages = Math.ceil(this.totalCount / this.pageSize);
    let left = this.currentPage - 2;
    let right = this.currentPage + 3;
    var l;
    let pagesRange = [];
    let pageNumArray = [];
    for (let i = 1; i <= this.totalPages; i++) {
      if (i == 1 || i == this.totalPages || (i >= left && i < right)) {
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
    this.pageNumberArray = pageNumArray
  }
  changePage(pageNumber: number | string){
    let parsedPageNumber = Number(pageNumber);
    if (!isNaN(parsedPageNumber) && parsedPageNumber != this.currentPage){
      this.currentPage = parsedPageNumber
      this.pageChangeEvent.emit(this.currentPage)
      this.pageNumbers()
    }
  }
  fetchPreviousPage(){
    if (this.currentPage > 1) {
      this.currentPage --;
      this.pageChangeEvent.emit(this.currentPage)
      this.pageNumbers()
    }
  }
  fetchNextPage(){
    if (this.totalPages > this.currentPage) {
      this.currentPage ++;
      this.pageChangeEvent.emit(this.currentPage)
      this.pageNumbers()
    }
  }
  ngOnChanges(changes: SimpleChanges) {
    this.pageNumbers()
  }
}
