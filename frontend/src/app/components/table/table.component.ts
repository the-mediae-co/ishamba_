import { Component, OnInit } from '@angular/core';

interface Product {
  name: string;
  category: string;
  brand: string;
  description: string;
  price: number;
}

@Component({
  selector: 'app-table',
  templateUrl:'./table.component.html',
  styleUrls: ['./table.component.css']
})
export class TableComponent implements OnInit {
  allProducts: Array<Product> = [
    { name : "Apple iMac 27-inch",category: 'PC',brand: 'Apple',description: 'Apple iMac 27-inch with Retina 5K display',price : 2999,},
    { name : "Apple MacBook Pro 13-inch", category: 'Laptop', brand: 'Apple', description: 'Apple MacBook Pro 13-inch with M1 chip', price : 1299,},
    { name : "Apple iPad Pro 12.9-inch", category: 'Tablet', brand: 'Apple', description: 'Apple iPad Pro 12.9-inch with M1 chip', price : 1099, },
    { name : "Apple iPhone 12 Pro Max", category: 'Smartphone', brand: 'Apple', description: 'Apple iPhone 12 Pro Max with 5G', price : 1099 },
    { name : "Apple Watch Series 6", category: 'Smartwatch', brand: 'Apple', description: 'Apple Watch Series 6 with GPS', price : 3999 },
    { name : "Apple AirPods Pro", category: 'Headphone', brand: 'Apple', description: 'Apple AirPods Pro with Active Noise Cancellation', price : 249,},
    { name : "Apple HomePod mini", category: 'Speaker', brand: 'Apple', description: 'Apple HomePod mini with Siri', price : 99,},
    { name : "Apple TV 4K", category: 'TV', brand: 'Apple', description: 'Apple TV 4K with Dolby Vision', price : 179, },
    { name : "Apple AirTag", category: 'Tracker', brand: 'Apple', description: 'Apple AirTag with Precision Finding', price : 29, },
    { name : "Apple MagSafe Charger", category: 'Charger', brand: 'Apple', description: 'Apple MagSafe Charger for iPhone 12', price : 39,},
    { name : "Apple USB-C Power Adapter", category: 'Adapter', brand: 'Apple', description: 'Apple USB-C Power Adapter for MacBook Pro', price : 69, },
    { name : "Apple USB-C to Lightning Cable", category: 'Cable', brand: 'Apple', description: 'Apple USB-C to Lightning Cable for iPhone', price : 19,},
    { name : "Apple iMac 27-inch",category: 'PC',brand: 'Apple',description: 'Apple iMac 27-inch with Retina 5K display',price : 2999,},
    { name : "Apple MacBook Pro 13-inch", category: 'Laptop', brand: 'Apple', description: 'Apple MacBook Pro 13-inch with M1 chip', price : 1299,},
    { name : "Apple iPad Pro 12.9-inch", category: 'Tablet', brand: 'Apple', description: 'Apple iPad Pro 12.9-inch with M1 chip', price : 1099, },
    { name : "Apple iPhone 12 Pro Max", category: 'Smartphone', brand: 'Apple', description: 'Apple iPhone 12 Pro Max with 5G', price : 1099 },
    { name : "Apple Watch Series 6", category: 'Smartwatch', brand: 'Apple', description: 'Apple Watch Series 6 with GPS', price : 3999 },
    { name : "Apple AirPods Pro", category: 'Headphone', brand: 'Apple', description: 'Apple AirPods Pro with Active Noise Cancellation', price : 249,},
    { name : "Apple HomePod mini", category: 'Speaker', brand: 'Apple', description: 'Apple HomePod mini with Siri', price : 99,},
    { name : "Apple TV 4K", category: 'TV', brand: 'Apple', description: 'Apple TV 4K with Dolby Vision', price : 179, },
    { name : "Apple AirTag", category: 'Tracker', brand: 'Apple', description: 'Apple AirTag with Precision Finding', price : 29, },
    { name : "Apple MagSafe Charger", category: 'Charger', brand: 'Apple', description: 'Apple MagSafe Charger for iPhone 12', price : 39,},
    { name : "Apple USB-C Power Adapter", category: 'Adapter', brand: 'Apple', description: 'Apple USB-C Power Adapter for MacBook Pro', price : 69, },
    { name : "Apple USB-C to Lightning Cable", category: 'Cable', brand: 'Apple', description: 'Apple USB-C to Lightning Cable for iPhone', price : 19,},
  ]

  currentPage: number = 1
  pageSize: number = 5

  filterBy: string[] = ['PC','Laptop','Tablet','Smartphone','Smartwatch','Headphone','Speaker','TV','Tracker','Charger','Adapter','Cable']

  filteredProduct: Array<Product> = this.allProducts

  columns: string[] = ['id','name', 'category', 'brand', 'description', 'price']

  ngOnInit(): void {
    this.displayData()
    this.pageNumbers()
  }
  constructor() { }
  
  displayData(){
    let startIndex = (this.currentPage - 1) * this.pageSize
    let endIndex = startIndex + this.pageSize
    return this.filteredProduct.slice(startIndex, endIndex)
  }
  nextPage(){
    this.currentPage++
    this.displayData()
  }

  previousPage(){
    this.currentPage--
    this.displayData()
  } 

  pageNumbers(){
    let totalPages = Math.ceil(this.filteredProduct.length / this.pageSize)
    let pageNumArray = new Array(totalPages)
    return pageNumArray
  }

  changePage(pageNumber: number){
    this.currentPage = pageNumber
    this.displayData()
  }

  filterData(searchTerm: string) {
    this.filteredProduct = this.allProducts.filter((product) => {
      return Object.values(product).some((val) => {
        if (typeof val === 'string') {
          return val.toLowerCase().includes(searchTerm.toLowerCase());
        }
        return false;
      });
    });
    this.displayData();
  }

  filterSelectedOption(selectedOption: string){
    this.filteredProduct = this.allProducts.filter((product) => {
      return product.category.toLowerCase().includes(selectedOption.toLowerCase());
    });
    this.displayData();
  }
  
}