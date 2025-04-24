import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';

import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import { MessagesComponent } from './messages/messages.component';
import { EnvironmentServiceProvider } from './services/environment.service.provider';
import { CustomerFileUploaderComponent } from './customer-file-uploader/customer-file-uploader.component';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { CustomersComponent } from './customers/customers.component';
import { HomeComponent } from './home/home.component';
import { DashboardComponent } from './dashboard/dashboard.component';
import { SettingsComponent } from './settings/settings.component';
import { TasksComponent } from './tasks/tasks.component';
import { CallCentersComponent } from './call-centers/call-centers.component';
import { CallsComponent } from './calls/calls.component';
import { CommoditiesComponent } from './commodities/commodities.component';
import { CommodityComponent } from './commodity/commodity.component';
import { BaseAPIService } from './services/base-api.service';
import { HttpClientModule } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { CookieService } from 'ngx-cookie-service';
import { TableComponent } from 'src/app/components/table/table.component';
import { NgxCsvParserModule } from 'ngx-csv-parser';
import { MessageRecipientsComponent } from './message-recipients/message-recipients.component';
import { NgxLoadingModule } from 'ngx-loading';
import { PaginatorComponent } from './components/paginator/paginator.component';
import { CustomerTableComponent } from './customers/customer-table/customer-table.component';
import { CustomerFilterPanelComponent } from './customers/customer-filter-panel/customer-filter-panel.component';

@NgModule({
  declarations: [
    AppComponent,
    MessagesComponent,
    CustomerFileUploaderComponent,
    CustomersComponent,
    HomeComponent,
    DashboardComponent,
    SettingsComponent,
    TasksComponent,
    CallCentersComponent,
    CallsComponent,
    CommoditiesComponent,
    CommodityComponent,
    TableComponent,
    MessageRecipientsComponent,
    PaginatorComponent,
    CustomerTableComponent,
    CustomerFilterPanelComponent,
  ],
  imports: [
    BrowserModule,
    AppRoutingModule,
    BrowserAnimationsModule,
    HttpClientModule,
    FormsModule,
    NgxCsvParserModule,
    NgxLoadingModule.forRoot({})
  ],
  providers: [EnvironmentServiceProvider, BaseAPIService, CookieService],
  bootstrap: [AppComponent]
})
export class AppModule { }
