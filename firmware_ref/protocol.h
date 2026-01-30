#include <stdint.h>
#include <stdbool.h>

#define RX_BUFFER_SIZE 1024
#define TX_BUFFER_SIZE 1024

typedef enum {
    MSG_HELLO_REQ = 0x01,
    MSG_HELLO_RSP = 0x02,
    MSG_DICT_REQ  = 0x03,
    MSG_DICT_RSP  = 0x04,
    MSG_PARAM_SET = 0x05,
    MSG_PARAM_GET = 0x06,
    MSG_TELEMETRY = 0x08,
    MSG_ACK       = 0x0A,
    MSG_ERROR     = 0x0B,
    MSG_TIME_SYNC = 0x0C,
    MSG_RUN_EXPERIMENT = 0x0D,
    MSG_EXPORT_LOG = 0x0E,
    MSG_APPLY_PROFILE = 0x0F
} MsgType;

typedef struct {
    uint8_t version;
    uint8_t msg_type;
    uint16_t seq;
    uint8_t flags;
    uint16_t payload_len;
} __attribute__((packed)) FrameHeader;

void Protocol_Init(void);
void Protocol_ProcessRx(void);
void Protocol_SendTelemetry(void);
void Protocol_SendAck(uint16_t seq);
