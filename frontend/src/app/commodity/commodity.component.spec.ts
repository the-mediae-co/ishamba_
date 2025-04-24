import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CommodityComponent } from './commodity.component';

describe('TipScheduleComponent', () => {
  let component: CommodityComponent;
  let fixture: ComponentFixture<CommodityComponent>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [CommodityComponent]
    });
    fixture = TestBed.createComponent(CommodityComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
