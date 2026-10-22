                items['최근출고일']=pd.to_datetime(items['최근출고일']).dt.strftime('%Y-%m-%d')
                st.dataframe(
                    items[['품명','매출액','점유율(%)','거래횟수','최근출고일']],
                    hide_index=True,use_container_width=True,height=340,
                    column_config={
                        '매출액':st.column_config.NumberColumn('매출액 (원)',format='%,.0f원'),
                        '점유율(%)':st.column_config.NumberColumn('점유율 (%)',format='%.1f%%'),
                        '거래횟수':st.column_config.NumberColumn('거래 건수',format='%,d'),
                        '최근출고일':st.column_config.TextColumn('최근 출고일')})
                st.caption(f'선택 기간 품목 매출 합계: {item_total:,.0f}원 · 품목 {len(items):,}개')
    with st.container(border=True):
        frame_section('🧾 최근 거래 내역')
        if customer_sales.empty:st.info('거래 내역이 없습니다.')
        else:
            cols=[c for c in ['출고일자','품명','규격','출고수량','단가','공급가액'] if c in customer_sales.columns]
            st.dataframe(customer_sales[cols].head(12),hide_index=True,use_container_width=True,height=300,
              column_config={'출고일자':st.column_config.DateColumn('출고일',format='YYYY-MM-DD'),
                             '공급가액':st.column_config.NumberColumn('공급가액',format='%,.0f원')})
    with st.container(border=True):
        frame_section('🏷️ 임대료 관련 내역')
        if rentals.empty:
            st.caption('매출 원본의 품명에 “임대료”가 포함된 내역이 없습니다. 실제 임대 계약이 없다는 의미는 아닙니다.')
        else:
            rent=rentals.copy()
            rent['월']=rent['출고일자'].dt.strftime('%Y-%m')
            groupcols=['품명']+(['규격'] if '규격' in rent else [])
            rental_summary=rent.groupby(groupcols,dropna=False).agg(최근청구일=('출고일자','max'),누적임대료=('공급가액','sum'),청구횟수=('공급가액','size')).reset_index()
            st.dataframe(rental_summary,hide_index=True,use_container_width=True)
            st.caption('월 임대료·계약 만료일·용기 수량은 계약 자료가 없으므로 자동 추정하지 않습니다.')

with right:
    with st.container(border=True):
        frame_section('🔔 내가 챙겨야 할 것')
        forecast=guess_next_orders(customer_sales)
        if not forecast.empty:
            st.caption('반복 출고 이력으로 계산한 참고 예상일 (확정 발주 아님)')
            st.dataframe(forecast[['품목','최근 출고일','평균 주기(일)','다음 예상 출고일']].head(5),hide_index=True,use_container_width=True)
            if st.button('예상 납품일을 할 일로 등록',use_container_width=True):
                for _,r in forecast.head(5).iterrows():
                    title=f'{r["품목"]} 납품 예상일 확인'
                    exists=records('tasks',code)
                    exists=exists[(exists['title']==title)&(exists['due']==str(r['다음 예상 출고일']))]
                    if exists.empty:save_record('tasks',dict(customer=code,title=title,due=str(r['다음 예상 출고일']),done=0))
                st.rerun()
        else:
            st.caption('일정한 출고 주기가 확인되지 않습니다. 정기 납품 일정은 직접 등록하세요.')
        try:
            tasks=records('tasks',code)
        except Exception as exc:
            st.error(f'할 일 조회 실패: {friendly_sheet_error(exc)}')
            tasks=pd.DataFrame(columns=SHEET_COLUMNS['tasks'])
        for _,r in tasks.iterrows():
            col_a,col_b=st.columns([8,1])
            with col_a:
                new=st.checkbox(f'{r["title"]}  ·  {r["due"] or "기한 미정"}',value=bool(r['done']),key=f'task_{r["id"]}')
                if new!=bool(r['done']):
                    write_or_warn(update_task,str(r['id']),new)
            with col_b:
                if st.button('✕',key=f'del_task_{r["id"]}',help='할 일 삭제'):
                    write_or_warn(delete_record,'tasks',str(r['id']))
        with st.expander('＋ 할 일 추가'):
            with st.form('new_task',clear_on_submit=True):
                title=st.text_input('확인할 업무',placeholder='예: 11월 정기 납품 일정 확인')
                due=st.date_input('확인 예정일',value=date.today())
                if st.form_submit_button('할 일 저장',use_container_width=True):
                    if title.strip():write_or_warn(save_record,'tasks',dict(customer=code,title=title.strip(),due=str(due),done=0))
                    else:st.warning('업무 내용을 입력하세요.')
    with st.container(border=True):
        frame_section('👤 담당자 / 거래처 메모')
        st.caption(f'거래처 코드: {code}  |  거래처명: {name} · 저장 시 Google Sheets에 함께 기록됩니다.')
        try:
            contacts=records('contacts',code)
        except Exception as exc:
            st.error(f'담당자 조회 실패: {friendly_sheet_error(exc)}')
            contacts=pd.DataFrame(columns=SHEET_COLUMNS['contacts'])
        ct=contacts.iloc[0].to_dict() if not contacts.empty else {}
        with st.form('contact_form'):
            person=st.text_input('업체 담당자',value=str(ct.get('contact_name') or ''))
            phone=st.text_input('연락처',value=str(ct.get('phone') or ''))
            email=st.text_input('이메일',value=str(ct.get('email') or ''))
            note=st.text_area('업체 특이사항 / 비고',value=str(ct.get('note') or ''),height=100,placeholder='예: 월말 마감, 매월 10일 전후 납품 협의')
            if st.form_submit_button('담당자 및 비고 저장',use_container_width=True):
                write_or_warn(save_contact,code,name,person,phone,email,note)

with st.container(border=True):
    frame_section('💬 커뮤니케이션 기록')
    st.caption('전화 · 메일 · 방문 · 미팅 내역을 업체별로 직접 기록합니다.')
    with st.expander('＋ 새 커뮤니케이션 기록',expanded=False):
        with st.form('new_log',clear_on_submit=True):
            x1,x2,x3=st.columns(3)
            day=x1.date_input('일자',value=date.today())
            method=x2.selectbox('구분',['전화','메일','방문','미팅','기타'])
            person=x3.text_input('상대 담당자')
            content=st.text_area('협의 내용',placeholder='예: 11월 헬륨 혼합가스 납품 일정 협의')
            next_action=st.text_input('후속 조치',placeholder='예: 10/20까지 견적서 회신')
            if st.form_submit_button('기록 저장',use_container_width=True):
                if content.strip():
                    write_or_warn(save_record,'logs',dict(customer=code,day=str(day),method=method,person=person.strip(),content=content.strip(),next_action=next_action.strip()))
                else:st.warning('협의 내용을 입력하세요.')
    try:
        logs=records('logs',code)
    except Exception as exc:
        st.error(f'소통 기록 조회 실패: {friendly_sheet_error(exc)}')
        logs=pd.DataFrame(columns=SHEET_COLUMNS['logs'])
    if logs.empty:st.info('아직 기록이 없습니다. 첫 통화나 메일 내용을 등록해 보세요.')
    else:
        for _,r in logs.head(20).iterrows():
            with st.expander(f'{r["day"]}  ·  {r["method"]}  ·  {str(r["content"])[:65]}'):
                st.write(f'**담당자:** {r["person"] or "미입력"}')
                st.write(r['content'])
                if r['next_action']:st.info(f'후속 조치: {r["next_action"]}')
                if st.button('이 기록 삭제',key=f'logdel_{r["id"]}'):
                    write_or_warn(delete_record,'logs',str(r['id']))

with st.expander('📥 개인 기록 백업 / 데이터 확인'):
    st.info('개인 영업 기록은 Google Sheets에 저장됩니다. 기록 저장과 ERP 원본 갱신은 서로 독립적입니다. 시트의 편집 권한을 가진 사람은 기록을 볼 수 있습니다.')
    try:
        all_logs=records('logs');all_tasks=records('tasks');all_contacts=records('contacts')
    except Exception as exc:
        st.error(f'백업 자료 조회 실패: {friendly_sheet_error(exc)}')
        all_logs=pd.DataFrame(columns=SHEET_COLUMNS['logs'])
        all_tasks=pd.DataFrame(columns=SHEET_COLUMNS['tasks'])
        all_contacts=pd.DataFrame(columns=SHEET_COLUMNS['contacts'])
    a,b,c=st.columns(3)
    a.download_button('커뮤니케이션 CSV',all_logs.to_csv(index=False).encode('utf-8-sig'),'커뮤니케이션_백업.csv','text/csv',use_container_width=True)
    b.download_button('할 일 CSV',all_tasks.to_csv(index=False).encode('utf-8-sig'),'할일_백업.csv','text/csv',use_container_width=True)
    c.download_button('담당자 CSV',all_contacts.to_csv(index=False).encode('utf-8-sig'),'담당자_백업.csv','text/csv',use_container_width=True)
    st.caption(f'거래처 {len(agency):,}개 / 매출 {len(sales):,}행 / 연결된 매출 파일 {sum(n in sources for n in SALES_FILES)}/4개')
