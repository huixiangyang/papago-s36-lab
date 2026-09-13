/* 仅对已验证 S36 主进程的固定一条指令做内存试验；重启即恢复原厂字节。 */
#define _GNU_SOURCE
#include <sys/ptrace.h>
#include <sys/wait.h>
#include <unistd.h>
#include <signal.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static volatile sig_atomic_t timed_out;
static void timeout_handler(int sig) { (void)sig; timed_out = 1; }
static int read_word(pid_t pid, uintptr_t address, uint32_t *value) {
    errno = 0;
    long word = ptrace(PTRACE_PEEKTEXT, pid, (void *)address, NULL);
    if (word == -1 && errno) return -1;
    *value = (uint32_t)word;
    return 0;
}
int main(int argc, char **argv) {
    if (argc != 3 || (strcmp(argv[2], "check") && strcmp(argv[2], "enable") && strcmp(argv[2], "restore"))) {
        fprintf(stderr, "usage: s36-mainstream-memory PID check|enable|restore\n");
        return 2;
    }
    char *end;
    errno = 0;
    long parsed = strtol(argv[1], &end, 10);
    if (errno || *end || parsed <= 1 || parsed > 4194304) return 2;
    pid_t pid = (pid_t)parsed;
    char link[64], exe[256];
    snprintf(link, sizeof(link), "/proc/%ld/exe", parsed);
    ssize_t n = readlink(link, exe, sizeof(exe)-1);
    if (n < 0) { perror("readlink"); return 1; }
    exe[n] = 0;
    if (strcmp(exe, "/app/bin/main_app")) {
        fprintf(stderr, "unexpected executable: %s\n", exe); return 1;
    }
    struct sigaction action = {0};
    action.sa_handler = timeout_handler;
    sigemptyset(&action.sa_mask);
    sigaction(SIGALRM, &action, NULL);
    if (ptrace(PTRACE_ATTACH, pid, NULL, NULL)) { perror("attach"); return 1; }
    int status = 0, result = 1, detach_signal = 0;
    alarm(5);
    pid_t waited;
    do { waited = waitpid(pid, &status, 0); } while (waited < 0 && errno == EINTR && !timed_out);
    alarm(0);
    if (waited != pid || !WIFSTOPPED(status)) { fprintf(stderr, "trace stop unavailable\n"); goto detach; }
    if (WSTOPSIG(status) != SIGSTOP) {
        detach_signal = WSTOPSIG(status);
        fprintf(stderr, "unrelated pending signal; no patch applied\n"); goto detach;
    }
    uint32_t load, compare, current;
    if (read_word(pid, 0x3c164, &load) || read_word(pid, 0x3c168, &compare) || read_word(pid, 0x3c16c, &current)) {
        perror("read instruction"); goto detach;
    }
    if (load != 0xe5933008 || compare != 0xe3530001 || (current != 0x1a00002c && current != 0x8a00002c)) {
        fprintf(stderr, "instruction fingerprint mismatch; no patch applied\n"); goto detach;
    }
    uint32_t desired = !strcmp(argv[2], "enable") ? 0x8a00002c : 0x1a00002c;
    if (strcmp(argv[2], "check") && current != desired) {
        /* ARM 内核的 POKETEXT 路径同时处理指令缓存，避免直接写 /proc/pid/mem。 */
        if (ptrace(PTRACE_POKETEXT, pid, (void *)(uintptr_t)0x3c16c, (void *)(uintptr_t)desired)) {
            perror("write instruction"); goto detach;
        }
        uint32_t actual;
        if (read_word(pid, 0x3c16c, &actual) || actual != desired) {
            ptrace(PTRACE_POKETEXT, pid, (void *)(uintptr_t)0x3c16c, (void *)(uintptr_t)current);
            fprintf(stderr, "verification failed; original instruction restoration attempted\n"); goto detach;
        }
        current = actual;
    }
    printf("pid=%ld instruction=%08x mode=%s\n", parsed, current, current == 0x8a00002c ? "main-and-sub" : "stock-sub-only");
    result = 0;
detach:
    if (ptrace(PTRACE_DETACH, pid, NULL, (void *)(uintptr_t)detach_signal)) {
        perror("detach"); result = 1;
    }
    return result;
}
