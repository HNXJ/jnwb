%% Header
%Takes all the NWB files currently on the preprocesser server and

function nwb_validation(SLACK_ID,IMAGE_TOKEN)

fprintf("Running the Validation Function ...\n")

%% pathing...can change to varargin or change function defaults for own machine
pp = pipelinePaths();

%add toolboxes
addpath(genpath("C:\Users\preprocess-server\Documents\GitHub\matnwb"));
addpath(genpath("C:\Users\preprocess-server\Documents\GitHub\SlackMatlab"));
generateCore();

%% Prepare slack
if exist('SLACK_ID', 'var')
    send_slack_alerts = true;
else
    send_slack_alerts = false;
end

%% Loop through sessions
old_dir = pwd;
cd(pp.NWB_DATA);
nwb_file_list = dir('*.nwb');
cd(old_dir);

for ii = 1:length(nwb_file_list)
    path_to_nwb = string(nwb_file_list(ii).folder) + "\";
    nwb_name = string(nwb_file_list(ii).name);

    try
        nwb = nwbRead(path_to_nwb + nwb_name);
        %Send this text to slack
        slack_text = sprintf("\n> Session %s\n", nwb.identifier);

        %Print out passive glo specific information
        try
            %Written by Hamed Nejat, to count the number of trials in passive
            %glo for each block, and trial types. Modified by Patrick Meng to
            %append to the slack notification text
            a = (nwb.intervals.get("passive_glo").vectordata.get("task_block_number").data(:) == 1) & nwb.intervals.get("passive_glo").vectordata.get("correct").data(:) & (nwb.intervals.get("passive_glo").vectordata.get("stimulus_number").data(:) == 5);
            b = (nwb.intervals.get("passive_glo").vectordata.get("task_block_number").data(:) == 2) & nwb.intervals.get("passive_glo").vectordata.get("correct").data(:) & (nwb.intervals.get("passive_glo").vectordata.get("stimulus_number").data(:) == 5);
            c = (nwb.intervals.get("passive_glo").vectordata.get("task_block_number").data(:) == 3) & nwb.intervals.get("passive_glo").vectordata.get("correct").data(:) & (nwb.intervals.get("passive_glo").vectordata.get("stimulus_number").data(:) == 5);
            d = (nwb.intervals.get("passive_glo").vectordata.get("task_block_number").data(:) == 4) & nwb.intervals.get("passive_glo").vectordata.get("correct").data(:) & (nwb.intervals.get("passive_glo").vectordata.get("stimulus_number").data(:) == 5);

            slack_text = slack_text + sprintf("\n\n->Total correct trials: %d\n", sum(a + b + c + d));
            slack_text = slack_text + sprintf("-> Habituation(1) = %d, Main(2) = %d, Random control(3) = %d, Sequence control(4) = %d \n", sum(a), sum(b), sum(c), sum(d));
            slack_text = slack_text + sprintf("\n--> (1) LO habituation : %d \n", sum(a));

            a = nwb.intervals.get("passive_glo").vectordata.get("go_gloexp").data(:) & nwb.intervals.get("passive_glo").vectordata.get("correct").data(:) & (nwb.intervals.get("passive_glo").vectordata.get("task_block_number").data(:) == 2);
            slack_text = slack_text + sprintf("\n--> (2) GO main : %d ", sum(a));
            b = nwb.intervals.get("passive_glo").vectordata.get("lo_gloexp").data(:) & nwb.intervals.get("passive_glo").vectordata.get("correct").data(:) & (nwb.intervals.get("passive_glo").vectordata.get("task_block_number").data(:) == 2);
            slack_text = slack_text + sprintf("\n--> (2) LO main : %d \n", sum(b));

            a = nwb.intervals.get("passive_glo").vectordata.get("go_rndctl").data(:) & nwb.intervals.get("passive_glo").vectordata.get("correct").data(:);
            slack_text = slack_text + sprintf("\n--> (3) GO random control : %d ", sum(a));
            b = nwb.intervals.get("passive_glo").vectordata.get("lo_rndctl").data(:) & nwb.intervals.get("passive_glo").vectordata.get("correct").data(:);
            slack_text = slack_text + sprintf("\n--> (3) LO random control : %d ", sum(b));

            c = nwb.intervals.get("passive_glo").vectordata.get("igo_rndctl").data(:) & nwb.intervals.get("passive_glo").vectordata.get("correct").data(:);
            slack_text = slack_text + sprintf("\n--> (3) iGO random control : %d ", sum(c));
            d = nwb.intervals.get("passive_glo").vectordata.get("ilo_rndctl").data(:) & nwb.intervals.get("passive_glo").vectordata.get("correct").data(:);
            slack_text = slack_text + sprintf("\n--> (3) iLO random control : %d ", sum(d));

            e = nwb.intervals.get("passive_glo").vectordata.get("rndctl").data(:) & nwb.intervals.get("passive_glo").vectordata.get("correct").data(:) & (nwb.intervals.get("passive_glo").vectordata.get("stimulus_number").data(:) == 5);
            slack_text = slack_text + sprintf("\n--> (3) Other random control : %d \n", sum(e) - sum(a + b + c + d));

            a = nwb.intervals.get("passive_glo").vectordata.get("go_seqctl").data(:) & nwb.intervals.get("passive_glo").vectordata.get("correct").data(:);
            slack_text = slack_text + sprintf("\n--> (4) GO sequence control : %d ", sum(a));
            b = nwb.intervals.get("passive_glo").vectordata.get("igo_seqctl").data(:) & nwb.intervals.get("passive_glo").vectordata.get("correct").data(:);
            slack_text = slack_text + sprintf("\n--> (4) iGO sequence control : %d \n", sum(b));

        catch
        end

        %Print out omission glo information
        try
            %Written by Hamed Nejat to count the trials in omission glo
            blocks = nwb.intervals.get("omission_glo_passive").vectordata.get("task_block_number").data(:);
            correct = nwb.intervals.get("omission_glo_passive").vectordata.get("correct").data(:);
            omission = nwb.intervals.get("omission_glo_passive").vectordata.get("is_omission").data(:);
            stims = nwb.intervals.get("omission_glo_passive").vectordata.get("stimulus_number").data(:);

            b1 = (blocks == 1) & (correct == 1) & (stims == 3);

            b2 = (blocks == 2) & (correct == 1) & (stims == 3);
            b2l = (blocks == 2) & (correct == 1) & (isnan(omission)) & (stims == 3);
            b2o2 = (blocks == 2) & (correct == 1) & (omission == 1) & (stims == 3);
            b2o3 = (blocks == 2) & (correct == 1) & (omission == 1) & (stims == 4);
            b2o4 = (blocks == 2) & (correct == 1) & (omission == 1) & (stims == 5);

            b3 = (blocks == 3) & (correct == 1) & (stims == 3);

            b4 = (blocks == 4) & (correct == 1) & (stims == 3);
            b4l = (blocks == 4) & (correct == 1) & (isnan(omission)) & (stims == 3);
            b4o2 = (blocks == 4) & (correct == 1) & (omission == 1) & (stims == 3);
            b4o3 = (blocks == 4) & (correct == 1) & (omission == 1) & (stims == 4);
            b4o4 = (blocks == 4) & (correct == 1) & (omission == 1) & (stims == 5);

            b5 = (blocks == 5) & (correct == 1) & (stims == 3);
            b5l = (blocks == 5) & (correct == 1) & (isnan(omission)) & (stims == 3);
            b5o2 = (blocks == 5) & (correct == 1) & (omission == 1) & (stims == 3);
            b5o3 = (blocks == 5) & (correct == 1) & (omission == 1) & (stims == 4);
            b5o4 = (blocks == 5) & (correct == 1) & (omission == 1) & (stims == 5);

            slack_text = slack_text + sprintf("\n->Total correct trials: %d\n", sum(b1 + b2 + b3 + b4 + b5));
            slack_text = slack_text + sprintf("-> AAAB(1) = %d, XAAAB(2) = %d, BBBA(3) = %d, XBBBA(4) = %d, XRRRR(5) = %d \n", sum(b1), sum(b2), sum(b3), sum(b4), sum(b5));
            slack_text = slack_text + sprintf("\n--> (1) AAAB habituation : %d \n", sum(b1));

            slack_text = slack_text + sprintf("\n--> (2) AAAB omission. omission chance : %f \n", sum(b2o2 + b2o3 + b2o4)/sum(b2));
            slack_text = slack_text + sprintf("\n--> (2) AAAB : %d \n", sum(b2l));
            slack_text = slack_text + sprintf("\n--> (2) AXAB : %d \n", sum(b2o2));
            slack_text = slack_text + sprintf("\n--> (2) AAXB : %d \n", sum(b2o3));
            slack_text = slack_text + sprintf("\n--> (2) AAAX : %d \n", sum(b2o4));

            slack_text = slack_text + sprintf("\n--> (3) BBBA habituation : %d \n", sum(b3));

            slack_text = slack_text + sprintf("\n--> (4) BBBA omission. omission chance : %f \n", sum(b4o2 + b4o3 + b4o4)/sum(b4));
            slack_text = slack_text + sprintf("\n--> (4) BBBA : %d \n", sum(b4l));
            slack_text = slack_text + sprintf("\n--> (4) BXBA : %d \n", sum(b4o2));
            slack_text = slack_text + sprintf("\n--> (4) BBXA : %d \n", sum(b4o3));
            slack_text = slack_text + sprintf("\n--> (4) BBBX : %d \n", sum(b4o4));

            slack_text = slack_text + sprintf("\n--> (5) RRRR omission. omission chance : %f \n", sum(b5o2 + b5o3 + b5o4)/sum(b5));
            slack_text = slack_text + sprintf("\n--> (5) RRRR : %d \n", sum(b5l));
            slack_text = slack_text + sprintf("\n--> (5) RXRR : %d \n", sum(b5o2));
            slack_text = slack_text + sprintf("\n--> (5) RRXR : %d \n", sum(b5o3));
            slack_text = slack_text + sprintf("\n--> (5) RRRX : %d \n", sum(b5o4));
        catch
        end

        %Print out active glo specific information
        try
            %Written by Hamed Nejat, to count the number of trials in passive
            %glo for each block, and trial types. Modified by Patrick Meng to
            %append to the slack notification text
            a = (nwb.intervals.get("active_glo").vectordata.get("task_block_number").data(:) == 1) & nwb.intervals.get("active_glo").vectordata.get("correct").data(:) & (nwb.intervals.get("active_glo").vectordata.get("stimulus_number").data(:) == 5);
            b = (nwb.intervals.get("active_glo").vectordata.get("task_block_number").data(:) == 2) & nwb.intervals.get("active_glo").vectordata.get("correct").data(:) & (nwb.intervals.get("active_glo").vectordata.get("stimulus_number").data(:) == 5);
            c = (nwb.intervals.get("active_glo").vectordata.get("task_block_number").data(:) == 3) & nwb.intervals.get("active_glo").vectordata.get("correct").data(:) & (nwb.intervals.get("active_glo").vectordata.get("stimulus_number").data(:) == 5);
            d = (nwb.intervals.get("active_glo").vectordata.get("task_block_number").data(:) == 4) & nwb.intervals.get("active_glo").vectordata.get("correct").data(:) & (nwb.intervals.get("active_glo").vectordata.get("stimulus_number").data(:) == 5);

            slack_text = slack_text + sprintf("\n\n->Total correct trials: %d\n", sum(a + b + c + d));
            slack_text = slack_text + sprintf("-> Habituation(1) = %d, Main(2) = %d, Random control(3) = %d, Sequence control(4) = %d \n", sum(a), sum(b), sum(c), sum(d));
            slack_text = slack_text + sprintf("\n--> (1) LO habituation : %d \n", sum(a));

            a = nwb.intervals.get("active_glo").vectordata.get("go_gloexp").data(:) & nwb.intervals.get("active_glo").vectordata.get("correct").data(:) & (nwb.intervals.get("active_glo").vectordata.get("task_block_number").data(:) == 2);
            slack_text = slack_text + sprintf("\n--> (2) GO main : %d ", sum(a));
            b = nwb.intervals.get("active_glo").vectordata.get("lo_gloexp").data(:) & nwb.intervals.get("active_glo").vectordata.get("correct").data(:) & (nwb.intervals.get("active_glo").vectordata.get("task_block_number").data(:) == 2);
            slack_text = slack_text + sprintf("\n--> (2) LO main : %d \n", sum(b));

            a = nwb.intervals.get("active_glo").vectordata.get("go_rndctl").data(:) & nwb.intervals.get("active_glo").vectordata.get("correct").data(:);
            slack_text = slack_text + sprintf("\n--> (3) GO random control : %d ", sum(a));
            b = nwb.intervals.get("active_glo").vectordata.get("lo_rndctl").data(:) & nwb.intervals.get("active_glo").vectordata.get("correct").data(:);
            slack_text = slack_text + sprintf("\n--> (3) LO random control : %d ", sum(b));

            c = nwb.intervals.get("active_glo").vectordata.get("igo_rndctl").data(:) & nwb.intervals.get("active_glo").vectordata.get("correct").data(:);
            slack_text = slack_text + sprintf("\n--> (3) iGO random control : %d ", sum(c));
            d = nwb.intervals.get("active_glo").vectordata.get("ilo_rndctl").data(:) & nwb.intervals.get("active_glo").vectordata.get("correct").data(:);
            slack_text = slack_text + sprintf("\n--> (3) iLO random control : %d ", sum(d));

            e = nwb.intervals.get("active_glo").vectordata.get("rndctl").data(:) & nwb.intervals.get("active_glo").vectordata.get("correct").data(:) & (nwb.intervals.get("active_glo").vectordata.get("stimulus_number").data(:) == 5);
            slack_text = slack_text + sprintf("\n--> (3) Other random control : %d \n", sum(e) - sum(a + b + c + d));

            a = nwb.intervals.get("active_glo").vectordata.get("go_seqctl").data(:) & nwb.intervals.get("active_glo").vectordata.get("correct").data(:);
            slack_text = slack_text + sprintf("\n--> (4) GO sequence control : %d ", sum(a));
            b = nwb.intervals.get("active_glo").vectordata.get("igo_seqctl").data(:) & nwb.intervals.get("active_glo").vectordata.get("correct").data(:);
            slack_text = slack_text + sprintf("\n--> (4) iGO sequence control : %d \n", sum(b));

        catch
        end

        tasknames = nwb.intervals.keys();

        try
            for taskcnt = 1:numel(tasknames)
    
                taskname = tasknames{taskcnt};
                slack_text = slack_text + sprintf("\n\t->Subtask : %s\n", taskname);
    
                if numel(nwb.intervals.get(taskname).vectordata.keys()) > 5
    
    
                    correct = nwb.intervals.get(taskname).vectordata.get("correct").data(:);
                    blocks = nwb.intervals.get(taskname).vectordata.get("task_block_number").data(:);
                    conditions = nwb.intervals.get(taskname).vectordata.get("task_condition_number").data(:);
                    stims = nwb.intervals.get(taskname).vectordata.get("stimulus_number").data(:);
        
                    x1 = (correct == 1) & (stims == 2);
                    x2 = numel(unique(blocks));
                    x3 = numel(unique(conditions));
                    x4 = (stims == 2);
        
                    slack_text = slack_text + sprintf("\n->Total correct trials: %d", sum(x1));
                    slack_text = slack_text + sprintf("\n-->Total blocks: %d", sum(x2));
                    slack_text = slack_text + sprintf("\n-->Total conditions: %d\n", sum(x3));
        
                    for i = 1:max(conditions)
        
                        cond_cnt = sum((conditions == i) & (stims == 2));
                        cond_correct = sum((conditions == i) & (correct == 1) & (stims == 2));
                        slack_text = slack_text + sprintf("\n--->Condition %d : %d trials, %d correct", i, sum(cond_cnt), sum(cond_correct));
        
                    end
        
                    slack_text = slack_text + sprintf("\n->Total trials: %d\n\n", sum(x4));
    
                end
    
            end
        catch

        end

        %Print out probe information
        try
            ProbeNames = unique(nwb.general_extracellular_ephys_electrodes.vectordata.get('probe').data(:));
            numProbes = length(ProbeNames);
            for p = 1:numProbes
                slack_text = slack_text + sprintf("\nProbe %d: " + string(nwb.general_extracellular_ephys.get(ProbeNames{p}).location),p-1);
            end
        catch
        end

        try
            %Add the good unit count
            slack_text = slack_text + sprintf("\nGood Units: %d",sum(nwb.units.vectordata.get('quality').data(:)));
        catch
            slack_text = slack_text + sprintf("\nNo units found ): \n");
        end

        if send_slack_alerts
            SendSlackNotification( ...
                SLACK_ID, ...
                [char(slack_text)], ...
                'nwb-validation', ...
                'HumanErrorExterminator', ...
                '', ...
                ':credit_card:');
        end


        disp(slack_text);

        %Add some CSD based on flash task, written by Maxwell Lichtenfield
        %     try
        %         sampleRate = 1000;
        %         preStim_time = 1000;
        %         postStim_time = 1000;
        %         flash_time_intervals = nwb.intervals.get('flash').start_time.data(:);
        %         flash_dataVect = nwb.intervals.get('flash').vectordata.get('codes').data(:); dataVect(isnan(dataVect)) = 0;
        %         flash_logical = find(nwb.intervals.get('flash').vectordata.get('correct').data(:) == 1);
        %         flash_loexp_logical = find(flash_dataVect(flash_logical) == 100);
        %         flash_time_intervals = nwb.intervals.get('flash').start_time.data(:);
        %         flash_loexp_startimes = flash_time_intervals(flash_loexp_logical)*sampleRate;
        %         if contains(probeInfo_A(1),'DBC')
        %             csd_lfp_A =  zeros(128,(preStim_time+postStim_time+1),size(flash_loexp_startimes,1));
        %             csd_lfp_B =  zeros(128,(preStim_time+postStim_time+1),size(flash_loexp_startimes,1));
        %             csd_lfp_C =  zeros(128,(preStim_time+postStim_time+1),size(flash_loexp_startimes,1));
        %         else
        %             csd_lfp_A =  zeros(32,(preStim_time+postStim_time+1),size(flash_loexp_startimes,1));
        %             csd_lfp_B =  zeros(32,(preStim_time+postStim_time+1),size(flash_loexp_startimes,1));
        %             csd_lfp_C =  zeros(32,(preStim_time+postStim_time+1),size(flash_loexp_startimes,1));
        %         end
        %         for n = 1:size(flash_loexp_startimes,1)
        %             csd_lfp_A(:,:,n) = nwb.acquisition.get('probe_0_lfp').electricalseries.get('probe_0_lfp_data').data(:,(flash_loexp_startimes(n)-preStim_time):(flash_loexp_startimes(n)+postStim_time));
        %             if  NumProbes >= 2
        %                 csd_lfp_B(:,:,n) = nwb.acquisition.get('probe_1_lfp').electricalseries.get('probe_1_lfp_data').data(:,(flash_loexp_startimes(n)-preStim_time):(flash_loexp_startimes(n)+postStim_time));
        %             elseif NumProbes == 3
        %                 csd_lfp_C(:,:,n) = nwb.acquisition.get('probe_2_lfp').electricalseries.get('probe_2_lfp_data').data(:,(flash_loexp_startimes(n)-preStim_time):(flash_loexp_startimes(n)+postStim_time));
        %             end
        %         end
        %         test = 3;
        %     catch
        %     end

        %     slack_text = "\n\n";
        %     %Joule Receptive field map, written by Hamed Nejat
        %     try
        %         ProbeNames = unique(nwb.general_extracellular_ephys_electrodes.vectordata.get('probe').data(:));
        %         numProbes = length(ProbeNames);
        %         identifier_ = nwb.identifier;
        %         for p = 1:length(numProbes)
        %             ProbeAreas{p} = nwb.general_extracellular_ephys.get(ProbeNames{p}).location;
        %
        %             fprintf("\n-> %d Probes detected in %s\n-->This function will process only probe no.%d (%s)", numProbes, identifier_, p, ProbeAreas{p}{1});
        %
        %             start_times= nwb.intervals.get('rf_mapping_v2').start_time.data(:);
        %             rf_info=nwb.intervals.get('rf_mapping_v2');
        %             correct = rf_info.vectordata.get('correct').data(:);
        %             x_position = rf_info.vectordata.get('x_position').data(:);
        %             x_position_negative = rf_info.vectordata.get('x_position_negative').data(:);
        %             y_position = rf_info.vectordata.get('y_position').data(:);
        %             y_position_negative = rf_info.vectordata.get('y_position_negative').data(:);
        %             sizes = rf_info.vectordata.get('size').data(:);
        %             trials = rf_info.vectordata.get('trial_num').data(:);
        %
        %             indx_correct_trls_from_all_events = find(~isnan(x_position) & correct);
        %             xpos = x_position;
        %             ypos = y_position;
        %             xnegs = find(x_position_negative);
        %             ynegs = find(y_position_negative);
        %
        %             xpos(xnegs) = -xpos(xnegs);
        %             ypos(ynegs) = -ypos(ynegs);
        %
        %             r = sizes;
        %             r = r(indx_correct_trls_from_all_events);
        %             xpos = xpos(indx_correct_trls_from_all_events);
        %             ypos = ypos(indx_correct_trls_from_all_events);
        %
        %             conds = [xpos ypos r];
        %             uniconds = unique(conds,'rows');
        %             condindx = nan(1,size(conds,1));
        %
        %             for cond = 1:length(uniconds)
        %                 for c = 1:size(conds,1)
        %                     if conds(c,:) == uniconds(cond,:)
        %                         condindx(c)=cond;
        %                     end
        %                 end
        %             end
        %
        %             mua_name = ['probe_',num2str(p-1),'_muae'];
        %             PD = nwb.acquisition.get('photodiode_1_tracking').timeseries.get('photodiode_1_tracking_data');
        %             % PD_data = PD.data(:);
        %             mua = nwb.acquisition.get(mua_name).electricalseries.get([mua_name,'_data']);
        %             indx = nearest_index(mua.timestamps(:),start_times(indx_correct_trls_from_all_events));
        %             resp = epoch_data(mua.data(:,:),indx,[200,200]);
        %             resp = baseline_correct(resp, 1:400);
        %
        %             for chan = 1:size(resp, 1)
        %
        %                 for cond = 1:length(uniconds)
        %                     chanresp(cond) = squeeze(mean(resp(chan,[226+50:226+80],condindx==cond),[2,3]));
        %                 end
        %
        %                 % chanresp(31) = 0;
        %                 even_indx = 1:size(resp, 1);
        %                 for cond = 1:length(uniconds)
        %                     chanresp_grandavg(cond) = squeeze(mean(resp(even_indx,[230:300],condindx==cond),[1,2,3]));
        %                 end
        %                 %chanresp_grandavg = chanresp_grandavg./max(chanresp_grandavg);
        %                 chanresp_grandavg = zscore(chanresp_grandavg);
        %                 % chanresp_grandavg(31) = 0;
        %
        %                 if mod(chan-1, 9) == 0
        %                     figure("Position", [0 0 1800 1400]);
        %                 end
        %
        %                 subplot(3, 3, mod(chan-1, 9)+1);
        %                 b = bubblechart(uniconds(:,1),uniconds(:,2),uniconds(:,3),chanresp);
        %                 bubblesize([4 27]);
        %                 colormap(gca,"jet");
        %                 % caxis([-3 3]);
        %                 colorbar;
        %                 title(num2str(chan));
        %                 set(gcf,'position',[50 50 1750 1350]);
        %             end
        %
        %             unix = uniconds(:,1);
        %             uniy = uniconds(:,2);
        %
        %             xu = unix;
        %             yu = uniy;
        %
        %             figure("Position", [0 0 1800 1200]);
        %             b = bubblechart(xu,yu,uniconds(:,3),chanresp_grandavg);
        %             colormap(gca,"jet");
        %             %caxis([0.7 1])
        %             colorbar;
        %             title("RF map for " + string(ProbeAreas{p}{p}));
        %             set(gcf,'position',[100 100 1300 1300]);
        %             fig_file_path = [pp.FIG_DATA nwb.identifier filesep];
        %             file_name = [nwb.identifier '_RF_MAP_area-' ProbeAreas{p}{p} '.png'];
        %             saveas(gcf,fig_file_path+file_name);
        %             pyrunfile('slack-uload.py',token=IMAGE_TOKEN,chan_name = 'nwb-validation',chart_path = fig_file_path+file_name);
        %         end
        %     catch
        %     end
        %
        %     if send_slack_alerts
        %         SendSlackNotification( ...
        %             SLACK_ID, ...
        %             [char(slack_text)], ...
        %             'nwb-validation', ...
        %             'HumanErrorExterminator', ...
        %             '', ...
        %             ':credit_card:');
        %     end
        %
        %     %Just to not rate limit in case there's a bunch of files that need
        %     %processing, pauses the code for 2 seconds
        %     pause(2)
    catch
        slack_text = "Could not open nwb file" + path_to_nwb + nwb_name;
        if send_slack_alerts
            SendSlackNotification( ...
                SLACK_ID, ...
                [char(slack_text)], ...
                'nwb-validation', ...
                'HumanErrorExterminator', ...
                '', ...
                ':credit_card:');
        end
    end

    disp('Validation Complete');

end

end