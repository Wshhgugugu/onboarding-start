module spi_peripheral (
    input wire clk,
    input wire rst_n,
    input wire nCS,
    input wire SCLK,
    input wire COPI,
    output reg [7:0] en_reg_out_7_0,
    output reg [7:0] en_reg_out_15_8,
    output reg [7:0] en_reg_pwm_7_0,
    output reg [7:0] en_reg_pwm_15_8,
    output reg [7:0] pwm_duty_cycle
);

    reg [2:0] sclk_sync;
    reg [1:0] copi_sync;
    reg [2:0] ncs_sync;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sclk_sync <= 3'b000;
            copi_sync <= 2'b00;
            ncs_sync  <= 3'b111;
        end else begin
            sclk_sync <= {sclk_sync[1:0], SCLK};
            copi_sync <= {copi_sync[0], COPI};
            ncs_sync  <= {ncs_sync[1:0], nCS};
        end
    end

    wire sclk_rising = !sclk_sync[2] &&  sclk_sync[1];
    wire ncs_rising  = !ncs_sync[2]  &&  ncs_sync[1]; 
    wire ncs_synced  =  ncs_sync[1];
    wire copi_synced =  copi_sync[1];

    reg [15:0] shift_reg;
    reg [3:0]  bit_count;
    reg        transaction_ready;
    reg [15:0] latched_data;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            shift_reg         <= 16'b0;
            bit_count         <= 4'b0;
            transaction_ready <= 1'b0;
            latched_data      <= 16'b0;
        end else begin
            if (!ncs_synced) begin
                if (sclk_rising) begin
                    shift_reg <= {shift_reg[14:0], copi_synced};
                    bit_count <= bit_count + 1;
                end
            end else begin
                if (ncs_rising && bit_count == 4'd0 && shift_reg != 16'b0) begin
                    latched_data      <= shift_reg;
                    transaction_ready <= 1'b1;
                end else if (transaction_processed) begin
                    transaction_ready <= 1'b0;
                end
                bit_count <= 4'b0;
                shift_reg <= 16'b0;
            end
        end
    end

    reg transaction_processed;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            en_reg_out_7_0        <= 8'b0;
            en_reg_out_15_8       <= 8'b0;
            en_reg_pwm_7_0        <= 8'b0;
            en_reg_pwm_15_8       <= 8'b0;
            pwm_duty_cycle        <= 8'b0;
            transaction_processed <= 1'b0;
        end else if (transaction_ready && !transaction_processed) begin
            if (latched_data[15] == 1'b1) begin
                case (latched_data[14:8])
                    7'h00: en_reg_out_7_0  <= latched_data[7:0];
                    7'h01: en_reg_out_15_8 <= latched_data[7:0];
                    7'h02: en_reg_pwm_7_0  <= latched_data[7:0];
                    7'h03: en_reg_pwm_15_8 <= latched_data[7:0];
                    7'h04: pwm_duty_cycle  <= latched_data[7:0];
                    default: ;
                endcase
            end
            transaction_processed <= 1'b1;
        end else if (!transaction_ready && transaction_processed) begin
            transaction_processed <= 1'b0;
        end
    end

endmodule